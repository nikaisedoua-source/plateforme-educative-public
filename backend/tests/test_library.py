"""Phase 2 : bibliothèque documentaire (import, extraction, découpage, validation, publication, captures)."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app import extraction, storage
from test_api import client, create_user  # noqa: F401  (fixture partagée)

DEMO_TXT = """Fiche DEMO — Mathématiques 6ème (données de test, non publiables)

Exercice 1
Calculer 12 + 30 et expliquer la méthode utilisée pour poser l'addition.

Exercice 2
Un rectangle DEMO mesure 4 cm sur 3 cm. Calculer son périmètre puis son aire.

Corrigé
Exercice 1
12 + 30 = 42 : on additionne les dizaines puis les unités.
"""


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "storage_root", lambda: tmp_path)
    monkeypatch.setattr(extraction, "ocr_png", lambda png: "Exercice 1\nTexte DEMO reconnu par OCR sur une page scannée.")
    return tmp_path


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(client: TestClient) -> dict:
    return _auth(create_user(client, role="admin", email="admin@example.com"))


def _chapter(client: TestClient, admin: dict) -> dict:
    grade = client.post("/api/v1/admin/grades", json={"code": "6E", "name": "6ème DEMO"}, headers=admin).json()
    subject = client.post("/api/v1/admin/subjects", json={"code": "MATHS", "name": "Maths DEMO"}, headers=admin).json()
    chapter = client.post(
        "/api/v1/admin/chapters",
        json={"grade_id": grade["id"], "subject_id": subject["id"], "title": "Nombres DEMO"}, headers=admin,
    ).json()
    return {"grade": grade, "subject": subject, "chapter": chapter}


def _upload(client: TestClient, admin: dict, name: str, content: bytes, **form) -> dict:
    response = client.post("/api/v1/library/documents", files={"file": (name, content)}, data=form, headers=admin)
    assert response.status_code == 201, response.text
    return response.json()


def _extract(client: TestClient, admin: dict, document_id: int) -> dict:
    response = client.post(f"/api/v1/library/documents/{document_id}/extract", headers=admin)
    assert response.status_code == 202, response.text
    document = client.get(f"/api/v1/library/documents/{document_id}", headers=admin).json()
    assert document["status"] == "extracted", document
    return document


def test_library_is_admin_only(client: TestClient):
    assert client.get("/api/v1/library/documents").status_code == 401
    student = _auth(create_user(client, role="student", email="eleve@example.com"))
    assert client.get("/api/v1/library/documents", headers=student).status_code == 403
    upload = client.post("/api/v1/library/documents", files={"file": ("a.txt", b"x")}, headers=student)
    assert upload.status_code == 403


def test_upload_rejects_bad_format_and_duplicates(client: TestClient, admin: dict):
    bad = client.post("/api/v1/library/documents", files={"file": ("virus.exe", b"MZ")}, headers=admin)
    assert bad.status_code == 415
    first = _upload(client, admin, "fiche_demo.txt", DEMO_TXT.encode())
    assert first["status"] == "imported" and first["title"] == "fiche_demo"
    again = client.post("/api/v1/library/documents", files={"file": ("copie.txt", DEMO_TXT.encode())}, headers=admin)
    assert again.status_code == 409


def test_full_pipeline_extract_segment_validate_publish(client: TestClient, admin: dict):
    refs = _chapter(client, admin)
    document = _upload(client, admin, "fiche_demo.txt", DEMO_TXT.encode(), kind="exercices")
    _extract(client, admin, document["id"])
    pages = client.get(f"/api/v1/library/documents/{document['id']}/pages", headers=admin).json()
    assert pages and "Exercice 2" in pages[0]["text"] and pages[0]["method"] == "text"

    report = client.post(f"/api/v1/library/documents/{document['id']}/segment", headers=admin)
    assert report.status_code == 200, report.text
    assert report.json() == {"document_id": document["id"], "exercises_created": 2, "corrections_found": 1}
    assert client.post(f"/api/v1/library/documents/{document['id']}/segment", headers=admin).status_code == 409

    exercises = client.get(f"/api/v1/library/exercises?document_id={document['id']}", headers=admin).json()
    first, second = exercises
    assert first["source_number"] == "1" and first["status"] == "extracted" and not first["is_published"]
    assert first["correction"]["source_document_id"] == document["id"]
    assert "42" in first["correction"]["original_text"]
    assert second["correction"] is None
    assert first["assets"] == []  # page purement textuelle : aucune capture

    # Publication impossible avant validation ; validation impossible sans chapitre.
    action = f"/api/v1/library/exercises/{first['id']}/action"
    assert client.post(action, json={"action": "publish"}, headers=admin).status_code == 409
    assert client.post(action, json={"action": "validate"}, headers=admin).status_code == 422

    edited = client.patch(
        f"/api/v1/library/exercises/{first['id']}",
        json={"chapter_id": refs["chapter"]["id"], "statement": "Calculer 12 + 30 (énoncé reformulé DEMO)."},
        headers=admin,
    ).json()
    assert edited["status"] == "transformed"
    assert edited["original_text"] == first["original_text"]  # l'original n'est jamais réécrit
    assert edited["grade_id"] == refs["grade"]["id"] and edited["subject_id"] == refs["subject"]["id"]

    assert client.post(action, json={"action": "submit"}, headers=admin).json()["status"] == "pending_validation"
    assert client.post(action, json={"action": "validate"}, headers=admin).json()["status"] == "validated"
    published = client.post(action, json={"action": "publish"}, headers=admin).json()
    assert published["is_published"] and published["published_at"]

    # Une modification après validation dépublie et redemande une validation.
    changed = client.patch(f"/api/v1/library/exercises/{first['id']}", json={"statement": "Autre DEMO"}, headers=admin)
    assert changed.json()["status"] == "transformed" and not changed.json()["is_published"]
    assert client.delete(f"/api/v1/library/exercises/{first['id']}", headers=admin).status_code == 409
    archived = client.post(action, json={"action": "archive"}, headers=admin).json()
    assert archived["is_archived"]

    # Un exercice jamais validé peut être supprimé (mauvais découpage).
    assert client.delete(f"/api/v1/library/exercises/{second['id']}", headers=admin).status_code == 204

    audit = client.get(f"/api/v1/library/audit?entity_type=exercise&entity_id={first['id']}", headers=admin).json()
    assert {"update", "submit", "validate", "publish", "archive"} <= {entry["action"] for entry in audit}


def test_replace_segmentation_keeps_validated_exercises(client: TestClient, admin: dict):
    refs = _chapter(client, admin)
    document = _upload(client, admin, "fiche_demo.txt", DEMO_TXT.encode(), chapter_id=str(refs["chapter"]["id"]))
    _extract(client, admin, document["id"])
    client.post(f"/api/v1/library/documents/{document['id']}/segment", headers=admin)
    first = client.get(f"/api/v1/library/exercises?document_id={document['id']}", headers=admin).json()[0]
    assert first["chapter_id"] == refs["chapter"]["id"]  # classement du document recopié
    client.post(f"/api/v1/library/exercises/{first['id']}/action", json={"action": "validate"}, headers=admin)

    report = client.post(f"/api/v1/library/documents/{document['id']}/segment?replace=true", headers=admin).json()
    assert report["exercises_created"] == 1
    remaining = client.get(f"/api/v1/library/exercises?document_id={document['id']}", headers=admin).json()
    assert [e["source_number"] for e in remaining] == ["1", "2"]
    assert remaining[0]["id"] == first["id"] and remaining[0]["status"] == "validated"


def test_correction_editing_and_validation(client: TestClient, admin: dict):
    document = _upload(client, admin, "fiche_demo.txt", DEMO_TXT.encode())
    _extract(client, admin, document["id"])
    client.post(f"/api/v1/library/documents/{document['id']}/segment", headers=admin)
    second = client.get(f"/api/v1/library/exercises?document_id={document['id']}", headers=admin).json()[1]
    url = f"/api/v1/library/exercises/{second['id']}/correction"
    saved = client.put(
        url, json={"final_answer": "P = 14 cm ; A = 12 cm²", "source_document_id": document["id"], "source_page": 1},
        headers=admin,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "extracted" and "14 cm" in saved.json()["original_text"]
    updated = client.put(
        url, json={"original_text": "tentative", "final_answer": "P = 14 cm", "source_document_id": document["id"]},
        headers=admin,
    ).json()
    assert updated["status"] == "transformed" and "12 cm²" in updated["original_text"]
    assert client.post(f"{url}/validate", headers=admin).json()["status"] == "validated"
    missing = client.put(url, json={"final_answer": "x", "source_document_id": 999}, headers=admin)
    assert missing.status_code == 404


def _scanned_pdf() -> bytes:
    image = Image.new("RGB", (1240, 1754), "white")
    ImageDraw.Draw(image).rectangle((200, 300, 900, 800), outline="black", width=8)
    buffer = io.BytesIO()
    image.save(buffer, format="PDF", resolution=150)
    return buffer.getvalue()


def test_scanned_pdf_uses_ocr_and_gets_page_capture(client: TestClient, admin: dict):
    document = _upload(client, admin, "4_5951744891707984739.pdf", _scanned_pdf())
    _extract(client, admin, document["id"])
    page = client.get(f"/api/v1/library/documents/{document['id']}/pages", headers=admin).json()[0]
    assert page["method"] == "ocr" and "OCR" in page["text"]
    suggestion = client.get(f"/api/v1/library/documents/{document['id']}/identify", headers=admin).json()
    assert set(suggestion) == {"title", "grade", "subject", "kind", "series"}

    image = client.get(f"/api/v1/library/documents/{document['id']}/pages/1/image", headers=admin)
    assert image.status_code == 200 and image.content[:8] == b"\x89PNG\r\n\x1a\n"

    client.post(f"/api/v1/library/documents/{document['id']}/segment", headers=admin)
    exercise = client.get(f"/api/v1/library/exercises?document_id={document['id']}", headers=admin).json()[0]
    assert [(a["kind"], a["page_number"]) for a in exercise["assets"]] == [("page", 1)]
    asset = client.get(f"/api/v1/library/assets/{exercise['assets'][0]['id']}", headers=admin)
    assert asset.status_code == 200 and asset.headers["content-type"] == "image/png"


def test_docx_extraction(client: TestClient, admin: dict):
    from docx import Document as DocxDocument

    docx = DocxDocument()
    docx.add_paragraph("Devoir DEMO de français")
    docx.add_paragraph("Exercice 1")
    docx.add_paragraph("Relever les verbes conjugués du texte DEMO et donner leur temps.")
    buffer = io.BytesIO()
    docx.save(buffer)
    document = _upload(client, admin, "devoir.docx", buffer.getvalue())
    _extract(client, admin, document["id"])
    report = client.post(f"/api/v1/library/documents/{document['id']}/segment", headers=admin).json()
    assert report["exercises_created"] == 1


def test_classification_must_be_consistent(client: TestClient, admin: dict):
    refs = _chapter(client, admin)
    other = client.post("/api/v1/admin/grades", json={"code": "5E", "name": "5ème DEMO"}, headers=admin).json()
    response = client.post(
        "/api/v1/library/documents", files={"file": ("x.txt", b"Exercice 1 DEMO")},
        data={"grade_id": str(other["id"]), "chapter_id": str(refs["chapter"]["id"])}, headers=admin,
    )
    assert response.status_code == 422


def test_import_folder_classifies_from_path_and_content(client: TestClient, admin: dict, tmp_path_factory):
    from sqlalchemy import select

    from app.database import get_session_factory
    from app.importer import import_folder, is_unnamed
    from app.main import app
    from app.models import Document, Grade, Subject

    root = tmp_path_factory.mktemp("documents_organises")
    (root / "Mathématiques" / "6ème").mkdir(parents=True)
    (root / "Mathématiques" / "6ème" / "fiche_demo.txt").write_text(DEMO_TXT)
    (root / "Divers").mkdir()
    (root / "Divers" / "4_5951744891707984739.txt").write_text(
        "Devoir DEMO de Physique-Chimie — classe de Terminale C, E\nExercice 1\nCalculer une vitesse DEMO de 30 m/s.\n"
    )
    (root / "Divers" / "._4_5951744891707984739.txt").write_bytes(b"\x00")  # métadonnées macOS ignorées
    (root / "Mathématiques" / "6ème" / "zz_copie.txt").write_text(DEMO_TXT)  # doublon exact

    factory = app.dependency_overrides[get_session_factory]()
    report = import_folder(factory, root, create_referentials=True, segment=True, log=lambda *_: None)
    assert [reason for _, reason in report.skipped] == ["doublon du document n° 2"]
    by_file = {entry["file"]: entry for entry in report.imported}
    named = by_file["Mathématiques/6ème/fiche_demo.txt"]
    assert named["source"] == "dossier" and named["exercises"] == 2
    unnamed = by_file["Divers/4_5951744891707984739.txt"]
    assert unnamed["source"] == "contenu" and unnamed["subject"] == "Physique-Chimie"
    assert unnamed["grade"] == "Terminale" and unnamed["title"].startswith("Devoir DEMO")
    assert unnamed["series"] == ["Terminale C", "Terminale E"]
    with factory() as db:
        assert {g.code for g in db.scalars(select(Grade))} == {"6E", "TLE"}
        assert {s.name for s in db.scalars(select(Subject))} == {"Mathématiques", "Physique-Chimie"}
        devoir = db.scalar(select(Document).where(Document.original_filename.like("4_%")))
        assert devoir.kind == "devoir"
        assert [t.code for t in devoir.tracks] == ["TLE-C", "TLE-E"]
        assert devoir.exercises if hasattr(devoir, "exercises") else True
        from app.models import Exercise
        exercise = db.scalar(select(Exercise).where(Exercise.document_id == devoir.id))
        assert [t.code for t in exercise.tracks] == ["TLE-C", "TLE-E"]  # l'exercice hérite des séries
    assert is_unnamed("file (1)") and is_unnamed("Corigé 1") and not is_unnamed("Bac 2023 maths")


def test_series_are_never_mixed(client: TestClient, admin: dict):
    grade = client.post("/api/v1/admin/grades", json={"code": "TLE", "name": "Terminale DEMO"}, headers=admin).json()
    other = client.post("/api/v1/admin/grades", json={"code": "1RE", "name": "1ère DEMO"}, headers=admin).json()
    subject = client.post("/api/v1/admin/subjects", json={"code": "MATHS", "name": "Maths DEMO"}, headers=admin).json()
    chapter = client.post("/api/v1/admin/chapters", json={"grade_id": grade["id"], "subject_id": subject["id"],
                                                          "title": "Suites DEMO"}, headers=admin).json()
    tracks = {}
    for grade_id, code, name in ((grade["id"], "TLE-A", "Tle A"), (grade["id"], "TLE-C", "Tle C"),
                                 (other["id"], "1RE-C", "1ère C")):
        response = client.post("/api/v1/admin/tracks", json={"grade_id": grade_id, "code": code, "name": name,
                                                              "kind": "serie"}, headers=admin)
        assert response.status_code == 201, response.text
        tracks[code] = response.json()["id"]

    # Une série d'un autre niveau est refusée (une 1ère C n'est pas une Tle C).
    wrong = client.post("/api/v1/library/documents", files={"file": ("a.txt", DEMO_TXT.encode())},
                        data={"grade_id": str(grade["id"]), "track_ids": [str(tracks["1RE-C"])]}, headers=admin)
    assert wrong.status_code == 422

    document = _upload(client, admin, "tle_demo.txt", DEMO_TXT.encode(), chapter_id=str(chapter["id"]))
    assert document["track_ids"] == []
    _extract(client, admin, document["id"])
    client.post(f"/api/v1/library/documents/{document['id']}/segment", headers=admin)
    exercise = client.get("/api/v1/library/exercises", params={"document_id": document["id"]}, headers=admin).json()[0]
    blocked = client.post(f"/api/v1/library/exercises/{exercise['id']}/action", json={"action": "validate"},
                          headers=admin)
    assert blocked.status_code == 422 and "séries" in blocked.json()["detail"]

    updated = client.patch(f"/api/v1/library/exercises/{exercise['id']}", json={"track_ids": [tracks["TLE-C"]]},
                           headers=admin)
    assert updated.status_code == 200 and updated.json()["track_ids"] == [tracks["TLE-C"]]
    assert updated.json()["status"] == "transformed"
    ok = client.post(f"/api/v1/library/exercises/{exercise['id']}/action", json={"action": "validate"}, headers=admin)
    assert ok.status_code == 200, ok.text

    # Le document peut viser plusieurs séries ; les nouveaux exercices en héritent.
    patched = client.patch(f"/api/v1/library/documents/{document['id']}",
                           json={"track_ids": [tracks["TLE-A"], tracks["TLE-C"]]}, headers=admin)
    assert sorted(patched.json()["track_ids"]) == sorted([tracks["TLE-A"], tracks["TLE-C"]])
    manual = client.post("/api/v1/library/exercises", json={"document_id": document["id"], "page_start": 1,
                                                            "title": "Ajout DEMO", "statement": "Énoncé DEMO."},
                         headers=admin)
    assert manual.status_code == 201, manual.text
    assert sorted(manual.json()["track_ids"]) == sorted([tracks["TLE-A"], tracks["TLE-C"]])
