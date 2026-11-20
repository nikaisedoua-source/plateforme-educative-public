"""Phase 3 : espace d'exercices de l'élève (niveau et série respectés, correction côté serveur, accès au corrigé)."""

import pytest
from fastapi.testclient import TestClient

from app import extraction, publication, storage
from test_api import client, create_user  # noqa: F401

PASSWORD = "mot-de-passe-DEMO-123"


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "storage_root", lambda: tmp_path)
    monkeypatch.setattr(publication, "DEFAULT_AUTO", False)  # circuit de validation manuelle
    monkeypatch.setattr(extraction, "ocr_png", lambda png: "")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _student(client: TestClient, admin: dict, email: str, pseudo: str, grade_id: int, track_id: int | None) -> dict:
    body = {"email": email, "password": PASSWORD, "pseudo": pseudo, "grade_id": grade_id}
    if track_id:
        body["track_id"] = track_id
    registered = client.post("/api/v1/auth/register", json=body)
    assert registered.status_code == 201, registered.text
    headers = _auth(client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"])
    assert client.get("/api/v1/student/exercises", headers=headers).status_code == 403  # pas encore validé
    user_id = registered.json()["id"]
    decision = client.post(f"/api/v1/admin/enrollments/{user_id}/decision", json={"decision": "approve"}, headers=admin)
    assert decision.status_code == 200, decision.text
    return headers


@pytest.fixture
def world(client: TestClient) -> dict:
    admin = _auth(create_user(client, role="admin", email="admin@example.com"))
    tle = client.post("/api/v1/admin/grades", json={"code": "TLE", "name": "Terminale DEMO"}, headers=admin).json()
    first = client.post("/api/v1/admin/grades", json={"code": "1RE", "name": "1ère DEMO"}, headers=admin).json()
    maths = client.post("/api/v1/admin/subjects", json={"code": "MATHS", "name": "Maths DEMO"}, headers=admin).json()
    chapter = client.post("/api/v1/admin/chapters", json={"grade_id": tle["id"], "subject_id": maths["id"],
                                                          "title": "Suites DEMO"}, headers=admin).json()
    tracks = {}
    for code, name in (("TLE-A", "Tle A"), ("TLE-C", "Tle C")):
        tracks[code] = client.post("/api/v1/admin/tracks", json={"grade_id": tle["id"], "code": code, "name": name,
                                                                   "kind": "serie"}, headers=admin).json()["id"]
    document = client.post("/api/v1/library/documents", files={"file": ("demo.txt", b"Exercice 1\nDEMO")},
                           data={"grade_id": str(tle["id"]), "subject_id": str(maths["id"])}, headers=admin).json()

    def exercise(title: str, track: str, **values) -> int:
        created = client.post("/api/v1/library/exercises", json={
            "document_id": document["id"], "page_start": 1, "title": title, "statement": f"Énoncé {title} DEMO",
            "chapter_id": chapter["id"], "track_ids": [tracks[track]],
        }, headers=admin)
        assert created.status_code == 201, created.text
        exercise_id = created.json()["id"]
        if values:
            patched = client.patch(f"/api/v1/library/exercises/{exercise_id}", json=values, headers=admin)
            assert patched.status_code == 200, patched.text
        for action in ("validate", "publish"):
            done = client.post(f"/api/v1/library/exercises/{exercise_id}/action", json={"action": action}, headers=admin)
            assert done.status_code == 200, done.text
        return exercise_id

    qcm = exercise("QCM DEMO", "TLE-C", exercise_type="qcm", points=2, options=[
        {"label": "A", "text": "$u_n = 2n$", "is_correct": True},
        {"label": "B", "text": "$u_n = n^2$", "is_correct": False},
    ])
    numeric = exercise("Calcul DEMO", "TLE-C", exercise_type="numerique", expected_answer="2,5",
                       numeric_tolerance=0.01)
    serie_a = exercise("Exercice Tle A DEMO", "TLE-A")
    return {"admin": admin, "tle": tle, "first": first, "tracks": tracks, "qcm": qcm, "numeric": numeric,
            "serie_a": serie_a, "document": document}


def test_student_only_sees_own_grade_and_series(client: TestClient, world: dict):
    student_c = _student(client, world["admin"], "c@example.com", "EleveC", world["tle"]["id"], world["tracks"]["TLE-C"])
    student_a = _student(client, world["admin"], "a@example.com", "EleveA", world["tle"]["id"], world["tracks"]["TLE-A"])
    student_1 = _student(client, world["admin"], "p@example.com", "Eleve1", world["first"]["id"], None)

    seen_c = {e["id"] for e in client.get("/api/v1/student/exercises", headers=student_c).json()}
    seen_a = {e["id"] for e in client.get("/api/v1/student/exercises", headers=student_a).json()}
    assert seen_c == {world["qcm"], world["numeric"]}
    assert seen_a == {world["serie_a"]}  # jamais d'exercice Tle C pour un élève de Tle A
    assert client.get("/api/v1/student/exercises", headers=student_1).json() == []
    assert client.get(f"/api/v1/student/exercises/{world['qcm']}", headers=student_a).status_code == 404
    subjects = client.get("/api/v1/student/subjects", headers=student_c).json()
    assert subjects[0]["exercise_count"] == 2 and subjects[0]["chapters"][0]["title"] == "Suites DEMO"

    # Un exercice dépublié disparaît aussitôt.
    client.post(f"/api/v1/library/exercises/{world['numeric']}/action", json={"action": "unpublish"},
                headers=world["admin"])
    assert {e["id"] for e in client.get("/api/v1/student/exercises", headers=student_c).json()} == {world["qcm"]}
    # L'administrateur n'utilise pas l'espace élève.
    assert client.get("/api/v1/student/exercises", headers=world["admin"]).status_code == 403


def test_answers_are_graded_by_the_server_and_hidden_before_attempt(client: TestClient, world: dict):
    student = _student(client, world["admin"], "c@example.com", "EleveC", world["tle"]["id"], world["tracks"]["TLE-C"])
    view = client.get(f"/api/v1/student/exercises/{world['qcm']}", headers=student)
    assert view.status_code == 200
    assert "is_correct" not in view.text and "expected_answer" not in view.text
    assert view.json()["correction_available"] is False
    assert client.get(f"/api/v1/student/exercises/{world['qcm']}/correction", headers=student).status_code == 403

    options = {o["label"]: o["id"] for o in view.json()["options"]}
    wrong = client.post(f"/api/v1/student/exercises/{world['qcm']}/attempts", json={"option_ids": [options["B"]]},
                        headers=student)
    assert wrong.status_code == 201 and wrong.json()["result"] == "incorrect" and wrong.json()["score"] == 0
    assert wrong.json()["correction_available"] is True  # règle par défaut : après une première réponse
    too_fast = client.post(f"/api/v1/student/exercises/{world['qcm']}/attempts", json={"option_ids": [options["A"]]},
                           headers=student)
    assert too_fast.status_code == 429
    forged = client.post(f"/api/v1/student/exercises/{world['qcm']}/attempts", json={"option_ids": [999]},
                         headers=student)
    assert forged.status_code == 422
    # Le score ne peut pas être fourni par l'élève.
    cheat = client.post(f"/api/v1/student/exercises/{world['numeric']}/attempts",
                        json={"answer_text": "3", "score": 100}, headers=student)
    assert cheat.status_code == 422
    right = client.post(f"/api/v1/student/exercises/{world['numeric']}/attempts", json={"answer_text": "5/2"},
                        headers=student)
    assert right.json()["result"] == "correct" and right.json()["score"] == 1

    correction = client.get(f"/api/v1/student/exercises/{world['qcm']}/correction", headers=student).json()
    assert correction["correct_option_ids"] == [options["A"]]


def test_correction_access_rule_is_configurable(client: TestClient, world: dict):
    admin = world["admin"]
    student = _student(client, admin, "c@example.com", "EleveC", world["tle"]["id"], world["tracks"]["TLE-C"])
    assert client.put("/api/v1/library/settings/correction-access", json={"mode": "never"}, headers=student).status_code == 403
    rule = client.put("/api/v1/library/settings/correction-access",
                      json={"mode": "after_success_or_attempts", "attempts": 2}, headers=admin)
    assert rule.status_code == 200 and rule.json()["attempts"] == 2

    url = f"/api/v1/student/exercises/{world['numeric']}"
    first = client.post(f"{url}/attempts", json={"answer_text": "7"}, headers=student).json()
    assert first["correction_available"] is False and "2 essais" in first["correction_rule"]
    _age_attempts(client)
    second = client.post(f"{url}/attempts", json={"answer_text": "8"}, headers=student).json()
    assert second["correction_available"] is True
    client.get(f"{url}/correction", headers=student)
    _age_attempts(client)
    after = client.post(f"{url}/attempts", json={"answer_text": "2.5"}, headers=student).json()
    assert after["result"] == "correct" and after["after_correction"] is True  # ne compte pas pour la maîtrise
    summary = client.get(url, headers=student).json()
    assert summary["solved"] is False and summary["attempts"] == 3

    # Règle propre à un exercice : jamais de corrigé.
    client.patch(f"/api/v1/library/exercises/{world['qcm']}", json={"correction_access": "never"}, headers=admin)
    blocked = client.get(f"/api/v1/student/exercises/{world['qcm']}", headers=student).json()
    assert blocked["correction_available"] is False and "enseignant" in blocked["correction_rule"]


def _age_attempts(client: TestClient) -> None:
    """Recule l'horodatage des réponses (évite d'attendre réellement le délai anti-rafale)."""
    from datetime import timedelta

    from sqlalchemy import select

    from app.database import get_db
    from app.main import app
    from app.models import ExerciseAttempt

    db = next(app.dependency_overrides[get_db]())
    for attempt in db.scalars(select(ExerciseAttempt)):
        attempt.created_at = attempt.created_at - timedelta(seconds=10)
    db.commit()
    db.close()
