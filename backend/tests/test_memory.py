"""Phase 4 : répétition espacée, cartes mémoire (corrigées par le serveur ou auto-évaluées), séries jamais
mélangées, méthodes de mémorisation et réglages."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.spaced import DEFAULT_PARAMS, exercise_rating, next_state
from test_api import client, create_user  # noqa: F401
from test_student import _student, isolated_storage, world  # noqa: F401


def _schedule(**values):
    base = {"ease": 2.5, "interval_days": 0.0, "repetitions": 0, "lapses": 0}
    return SimpleNamespace(**(base | values))


def test_spaced_intervals_grow_and_failures_come_back_soon():
    first = next_state(_schedule(), 2, DEFAULT_PARAMS)
    assert first["interval_days"] == 1 and first["repetitions"] == 1 and first["mastery"] == "en_cours"
    second = next_state(_schedule(interval_days=1, repetitions=1), 2, DEFAULT_PARAMS)
    assert second["interval_days"] == 3
    third = next_state(_schedule(interval_days=3, repetitions=2), 2, DEFAULT_PARAMS)
    assert third["interval_days"] == 7.5  # 3 jours × facilité 2,5
    easy = next_state(_schedule(interval_days=10, repetitions=3), 3, DEFAULT_PARAMS)
    assert easy["interval_days"] > 21 and easy["mastery"] == "maitrise" and easy["ease"] > 2.5

    failed = next_state(_schedule(interval_days=30, repetitions=4, ease=1.35), 0, DEFAULT_PARAMS)
    assert failed["interval_days"] == 0 and failed["repetitions"] == 0 and failed["lapses"] == 1
    assert failed["delay"].total_seconds() == 600 and failed["ease"] == 1.3  # jamais sous la facilité minimale
    assert failed["mastery"] == "a_revoir"
    capped = next_state(_schedule(interval_days=170, repetitions=8), 3, DEFAULT_PARAMS)
    assert capped["interval_days"] == DEFAULT_PARAMS["max_interval_days"]


def test_success_after_reading_correction_is_never_mastery():
    assert exercise_rating("correct", after_correction=False) == 2
    assert exercise_rating("correct", after_correction=True) == 1
    assert exercise_rating("incorrect", after_correction=False) == 0
    assert exercise_rating("submitted", after_correction=False) is None


def _card(client: TestClient, world: dict, track: str, **values) -> int:
    admin = world["admin"]
    chapter = client.get("/api/v1/admin/chapters", headers=admin).json()[0]["id"]
    body = {"document_id": world["document"]["id"], "grade_id": world["tle"]["id"], "chapter_id": chapter,
            "track_ids": [world["tracks"][track]], "question": "Question DEMO", "answer": "Réponse DEMO"} | values
    created = client.post("/api/v1/memory/flashcards", json=body, headers=admin)
    assert created.status_code == 201, created.text
    card_id = created.json()["id"]
    for action in ("validate", "publish"):
        done = client.post(f"/api/v1/memory/flashcards/{card_id}/action", json={"action": action}, headers=admin)
        assert done.status_code == 200, done.text
    return card_id


def test_flashcards_follow_series_and_grading_rules(client: TestClient, world: dict):
    self_card = _card(client, world, "TLE-C")
    numeric = _card(client, world, "TLE-C", card_type="numerique", question="Combien vaut 5/2 ? DEMO", answer="2,5")
    other = _card(client, world, "TLE-A")
    student = _student(client, world["admin"], "c@example.com", "EleveC", world["tle"]["id"], world["tracks"]["TLE-C"])
    student_a = _student(client, world["admin"], "a@example.com", "EleveA", world["tle"]["id"], world["tracks"]["TLE-A"])

    assert client.get(f"/api/v1/student/flashcards/{other}", headers=student).status_code == 404  # séries
    assert client.get(f"/api/v1/student/flashcards/{self_card}", headers=student_a).status_code == 404
    session = client.get("/api/v1/student/revisions/today", headers=student)
    assert session.status_code == 200, session.text

    # Carte auto-évaluée : la réponse doit être affichée avant la note.
    url = "/api/v1/student/flashcards/{}/review"
    assert client.post(url.format(self_card), json={"rating": 3}, headers=student).status_code == 409
    assert client.get(f"/api/v1/student/flashcards/{self_card}/answer", headers=student).status_code == 200
    graded = client.post(url.format(self_card), json={"rating": 0}, headers=student)
    assert graded.status_code == 200 and graded.json()["mastery"] == "a_revoir"

    # Carte numérique : corrigée par le serveur, jamais auto-notée, réponse cachée avant d'avoir répondu.
    assert client.get(f"/api/v1/student/flashcards/{numeric}/answer", headers=student).status_code == 409
    assert client.post(url.format(numeric), json={"rating": 3, "answer_text": "2,5"}, headers=student).status_code == 422
    checked = client.post(url.format(numeric), json={"answer_text": "2.5"}, headers=student)
    assert checked.status_code == 200 and checked.json()["result"] == "correct"
    stats = client.get("/api/v1/student/revisions/stats", headers=student)
    assert stats.status_code == 200


def test_flashcard_needs_series_before_validation(client: TestClient, world: dict):
    admin = world["admin"]
    chapter = client.get("/api/v1/admin/chapters", headers=admin).json()[0]["id"]
    created = client.post("/api/v1/memory/flashcards", json={
        "document_id": world["document"]["id"], "grade_id": world["tle"]["id"], "chapter_id": chapter,
        "track_ids": [], "question": "Q DEMO", "answer": "R DEMO"}, headers=admin)
    assert created.status_code == 201, created.text
    refused = client.post(f"/api/v1/memory/flashcards/{created.json()['id']}/action", json={"action": "validate"},
                          headers=admin)
    assert refused.status_code == 422 and "séries" in refused.json()["detail"]
    wrong = client.post("/api/v1/memory/flashcards", json={
        "document_id": world["document"]["id"], "grade_id": world["tle"]["id"], "chapter_id": chapter,
        "track_ids": [world["tracks"]["TLE-C"]], "card_type": "vrai_faux", "question": "Q DEMO",
        "answer": "peut-être"}, headers=admin)
    assert client.post(f"/api/v1/memory/flashcards/{wrong.json()['id']}/action", json={"action": "validate"},
                       headers=admin).status_code == 422
    # un élève n'accède jamais à l'administration des cartes
    student = _student(client, admin, "c@example.com", "EleveC", world["tle"]["id"], world["tracks"]["TLE-C"])
    assert client.get("/api/v1/memory/flashcards", headers=student).status_code == 403


def test_methods_need_principle_and_steps(client: TestClient, world: dict):
    admin = world["admin"]
    methods = client.get("/api/v1/memory/methods", headers=admin).json()
    assert methods, "le catalogue de méthodes est créé au premier affichage"
    method = methods[0]
    client.patch(f"/api/v1/memory/methods/{method['id']}", json={"principle": "", "steps": []}, headers=admin)
    refused = client.post(f"/api/v1/memory/methods/{method['id']}/action", json={"action": "validate"}, headers=admin)
    assert refused.status_code == 422
    client.patch(f"/api/v1/memory/methods/{method['id']}", json={"principle": "Se tester DEMO",
                                                                  "steps": ["Cacher", "Réciter"]}, headers=admin)
    approved = client.post(f"/api/v1/memory/methods/{method['id']}/action", json={"action": "validate"}, headers=admin)
    assert approved.status_code == 200 and approved.json()["status"] == "validated"
    student = _student(client, admin, "c@example.com", "EleveC", world["tle"]["id"], world["tracks"]["TLE-C"])
    seen = client.get("/api/v1/student/methods", headers=student).json()
    assert method["id"] in [m["id"] for m in seen]
    # modifier une méthode approuvée la repasse en brouillon
    edited = client.patch(f"/api/v1/memory/methods/{method['id']}", json={"summary": "Autre DEMO"}, headers=admin)
    assert edited.json()["status"] == "draft"


@pytest.mark.parametrize("body, code", [
    ({"learning_steps_days": [1, 3], "relearn_minutes": 10, "min_ease": 1.3, "max_interval_days": 180,
      "mastery_interval_days": 21, "new_cards_per_day": 20}, 200),
    ({"learning_steps_days": [3, 1], "relearn_minutes": 10, "min_ease": 1.3, "max_interval_days": 180,
      "mastery_interval_days": 21, "new_cards_per_day": 20}, 422),
])
def test_spaced_settings(client: TestClient, world: dict, body, code):
    response = client.put("/api/v1/memory/settings/spaced-repetition", json=body, headers=world["admin"])
    assert response.status_code == code, response.text


def test_delegated_approval_writes_every_method_without_overwriting(client: TestClient, world: dict):
    """Décision du propriétaire (2026-11-20) : les méthodes sont rédigées et approuvées pour lui ; un texte déjà
    saisi par l'administrateur n'est jamais remplacé."""
    from sqlalchemy import select

    from app.database import get_db
    from app.main import app
    from app.methods_catalog import CATALOG, GUIDE, write_and_approve
    from app.models import MemoryMethod, User

    admin = world["admin"]
    methods = client.get("/api/v1/memory/methods", headers=admin).json()
    assert {m["code"] for m in methods} == set(GUIDE) == {c[0] for c in CATALOG}
    first = methods[0]
    client.patch(f"/api/v1/memory/methods/{first['id']}", json={"principle": "Texte admin DEMO",
                                                                 "steps": ["Étape DEMO"]}, headers=admin)
    db = next(app.dependency_overrides.get(get_db, get_db)())
    admin_id = db.scalar(select(User.id).where(User.role == "admin"))
    assert write_and_approve(db, admin_id) == len(CATALOG)
    kept = db.get(MemoryMethod, first["id"])
    assert kept.principle == "Texte admin DEMO" and kept.steps == ["Étape DEMO"]
    student = _student(client, admin, "d@example.com", "EleveD", world["tle"]["id"], world["tracks"]["TLE-C"])
    seen = client.get("/api/v1/student/methods", headers=student).json()
    assert len(seen) == len(CATALOG) and all(m["principle"] and m["steps"] for m in seen)
    assert write_and_approve(db, admin_id) == 0  # idempotent
