"""Sélection des exercices sur la page du document (décision utilisateur du 2026-11-20 : « sélectionne les
exercices au lieu de faire de la loterie »)."""

import pytest
from fastapi.testclient import TestClient

from app import extraction, publication, selection, storage
from app.models import Exercise
from test_api import client, create_user  # noqa: F401  (fixture partagée)
from test_library import DEMO_TXT, _auth, _chapter, _extract, _upload


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "storage_root", lambda: tmp_path)
    monkeypatch.setattr(publication, "DEFAULT_AUTO", True)
    monkeypatch.setattr(extraction, "ocr_png", lambda png: "")
    return tmp_path


def test_zone_must_be_inside_the_page():
    assert selection.Zone.parse({"page": 2, "top": 0.1, "bottom": 0.4}).right == 1.0
    for bad in ({"page": 1, "top": 0.5, "bottom": 0.4}, {"page": 1, "top": 0.1, "bottom": 1.2},
                {"page": 1, "top": 0.1, "bottom": 0.3, "left": 0.6, "right": 0.5}):
        with pytest.raises(ValueError):
            selection.Zone.parse(bad)


def test_only_examined_and_kept_exercises_are_published(client: TestClient):
    from app.database import get_session_factory
    from app.main import app

    session = app.dependency_overrides[get_session_factory]()
    admin = _auth(create_user(client, role="admin", email="admin@example.com"))
    refs = _chapter(client, admin)
    document = _upload(client, admin, "fiche_demo.txt", DEMO_TXT.encode(), chapter_id=str(refs["chapter"]["id"]))
    _extract(client, admin, document["id"])
    client.post(f"/api/v1/library/documents/{document['id']}/segment", headers=admin)

    with session() as db:
        first, second = db.query(Exercise).filter_by(document_id=document["id"]).order_by(Exercise.id).all()
        outcome = publication.publish(db, first, publication.datetime.now(publication.UTC), {})
        assert outcome == selection.NOT_SELECTED and not first.is_published  # plus de publication à l'aveugle

        assert selection.decide(db, first, True, "exercice complet DEMO", title="Additions DEMO — Exercice 1") == "publié"
        assert first.is_published and first.title == "Additions DEMO — Exercice 1"
        assert selection.decide(db, second, False, "activité de cours DEMO, pas un exercice") == selection.DROPPED
        assert not second.is_published
        db.commit()
        first_id = first.id

    # Un nouveau découpage du document ne supprime ni ne duplique un exercice examiné.
    client.post(f"/api/v1/library/documents/{document['id']}/segment?replace=true", headers=admin)
    with session() as db:
        rows = db.query(Exercise).filter_by(document_id=document["id"]).all()
        assert len(rows) == 2 and first_id in {e.id for e in rows}
        assert selection.kept_ids(db) == {first_id}
