"""Phase 1 : séries/spécialités, choix du parcours par l'élève et validation administrateur."""

from fastapi.testclient import TestClient

from test_api import client, create_user  # noqa: F401  (fixture partagée)

PASSWORD = "mot-de-passe-solide-2026"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _reference_data(client: TestClient, admin: dict) -> dict:
    grade = client.post("/api/v1/admin/grades", json={"code": "1RE", "name": "1re DEMO"}, headers=admin).json()
    other = client.post("/api/v1/admin/grades", json={"code": "TLE", "name": "Terminale DEMO"}, headers=admin).json()
    track = client.post(
        "/api/v1/admin/tracks",
        json={"grade_id": grade["id"], "code": "STMG-DEMO", "name": "STMG DEMO", "kind": "serie"},
        headers=admin,
    )
    assert track.status_code == 201, track.text
    class_group = client.post(
        "/api/v1/admin/classes",
        json={"grade_id": grade["id"], "name": "1re A DEMO", "academic_year": "2026-2027"},
        headers=admin,
    ).json()
    return {"grade": grade, "other": other, "track": track.json(), "class": class_group}


def _register(client: TestClient, email: str, pseudo: str, **parcours):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "pseudo": pseudo, **parcours},
    )


def _login(client: TestClient, email: str) -> dict:
    token = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
    return _auth(token)


def test_catalog_is_public_and_contains_no_student_data(client: TestClient):
    admin = _auth(create_user(client, role="admin", email="admin@example.com"))
    ref = _reference_data(client, admin)
    _register(client, "eleve@example.com", "EleveDEMO", grade_id=ref["grade"]["id"])

    response = client.get("/api/v1/catalog")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"cycles", "grades", "tracks", "classes"}
    assert [t["code"] for t in body["tracks"]] == ["STMG-DEMO"]
    assert "EleveDEMO" not in response.text and "eleve@example.com" not in response.text


def test_student_joins_parcours_at_registration_and_waits_for_validation(client: TestClient):
    admin = _auth(create_user(client, role="admin", email="admin@example.com"))
    ref = _reference_data(client, admin)
    response = _register(
        client, "eleve@example.com", "EleveDEMO",
        grade_id=ref["grade"]["id"], track_id=ref["track"]["id"], class_id=ref["class"]["id"],
    )
    assert response.status_code == 201, response.text
    profile = response.json()["profile"]
    assert profile["enrollment_status"] == "pending"
    assert profile["track_id"] == ref["track"]["id"]

    pending = client.get("/api/v1/admin/enrollments?status=pending", headers=admin).json()
    assert [p["pseudo"] for p in pending] == ["EleveDEMO"]
    user_id = pending[0]["user_id"]

    decision = client.post(f"/api/v1/admin/enrollments/{user_id}/decision", json={"decision": "approve"}, headers=admin)
    assert decision.status_code == 200, decision.text
    assert decision.json()["enrollment_status"] == "approved"

    me = client.get("/api/v1/auth/me", headers=_login(client, "eleve@example.com")).json()
    assert me["profile"]["enrollment_status"] == "approved"
    assert me["profile"]["class_id"] == ref["class"]["id"]

    again = client.post(f"/api/v1/admin/enrollments/{user_id}/decision", json={"decision": "reject"}, headers=admin)
    assert again.status_code == 409


def test_registration_without_parcours_then_joining_later(client: TestClient):
    admin = _auth(create_user(client, role="admin", email="admin@example.com"))
    ref = _reference_data(client, admin)
    assert _register(client, "eleve@example.com", "EleveDEMO").json()["profile"]["enrollment_status"] == "none"
    student = _login(client, "eleve@example.com")

    response = client.post("/api/v1/auth/me/enrollment", json={"grade_id": ref["grade"]["id"]}, headers=student)
    assert response.status_code == 200, response.text
    assert response.json()["enrollment_status"] == "pending"


def test_incoherent_parcours_is_refused(client: TestClient):
    admin = _auth(create_user(client, role="admin", email="admin@example.com"))
    ref = _reference_data(client, admin)
    wrong_track = _register(client, "a@example.com", "EleveA", grade_id=ref["other"]["id"], track_id=ref["track"]["id"])
    assert wrong_track.status_code == 422
    wrong_class = _register(client, "b@example.com", "EleveB", grade_id=ref["other"]["id"], class_id=ref["class"]["id"])
    assert wrong_class.status_code == 422
    missing_grade = _register(client, "c@example.com", "EleveC", track_id=ref["track"]["id"])
    assert missing_grade.status_code == 422
    unknown_grade = _register(client, "d@example.com", "EleveD", grade_id=9999)
    assert unknown_grade.status_code == 404


def test_student_cannot_approve_own_enrollment_or_create_tracks(client: TestClient):
    admin = _auth(create_user(client, role="admin", email="admin@example.com"))
    ref = _reference_data(client, admin)
    user_id = _register(client, "eleve@example.com", "EleveDEMO", grade_id=ref["grade"]["id"]).json()["id"]
    student = _login(client, "eleve@example.com")

    assert client.post(
        f"/api/v1/admin/enrollments/{user_id}/decision", json={"decision": "approve"}, headers=student,
    ).status_code == 403
    assert client.get("/api/v1/admin/enrollments", headers=student).status_code == 403
    assert client.post(
        "/api/v1/admin/tracks",
        json={"grade_id": ref["grade"]["id"], "code": "X-DEMO", "name": "X", "kind": "option"},
        headers=student,
    ).status_code == 403
    assert client.post("/api/v1/auth/me/enrollment", json={"grade_id": ref["grade"]["id"]}).status_code == 401


def test_admin_cannot_request_enrollment(client: TestClient):
    admin = _auth(create_user(client, role="admin", email="admin@example.com"))
    ref = _reference_data(client, admin)
    assert client.post("/api/v1/auth/me/enrollment", json={"grade_id": ref["grade"]["id"]}, headers=admin).status_code == 403
