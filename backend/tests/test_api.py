import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-that-is-long-enough-123456")
os.environ.setdefault("CORS_ORIGINS", "[]")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.security import hash_password


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_get_db():
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def create_user(client: TestClient, *, role: str, email: str) -> str:
    from app.database import get_db

    override = app.dependency_overrides[get_db]
    db_generator = override()
    db = next(db_generator)
    user = User(email=email, password_hash=hash_password("test-password-long-123"), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()
    token, _ = __import__("app.security", fromlist=["create_access_token"]).create_access_token(user_id)
    return token


def test_registration_always_creates_student_and_login_works(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "eleve@example.com", "password": "mot-de-passe-solide-2026", "pseudo": "Nikaise"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "student"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "eleve@example.com", "password": "mot-de-passe-solide-2026"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_public_registration_cannot_assign_admin_role(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "malveillant@example.com", "password": "mot-de-passe-solide-2026", "pseudo": "Eleve",
              "role": "admin"},
    )
    assert response.status_code == 422


def test_admin_routes_deny_anonymous_and_student(client: TestClient):
    assert client.post("/api/v1/admin/grades", json={"code": "6E", "name": "6me"}).status_code == 401
    student_token = create_user(client, role="student", email="eleve@example.com")
    response = client.post(
        "/api/v1/admin/grades",
        json={"code": "6E", "name": "6me"},
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 403


def test_admin_can_create_phase_one_reference_data(client: TestClient):
    token = create_user(client, role="admin", email="admin@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    cycle = client.post("/api/v1/admin/cycles", json={"code": "COLLEGE", "name": "Collge"}, headers=headers)
    assert cycle.status_code == 201, cycle.text
    grade = client.post(
        "/api/v1/admin/grades",
        json={"cycle_id": cycle.json()["id"], "code": "6E", "name": "6me"}, headers=headers,
    )
    assert grade.status_code == 201, grade.text
    class_group = client.post(
        "/api/v1/admin/classes",
        json={"grade_id": grade.json()["id"], "name": "6e A", "academic_year": "2026-2027"}, headers=headers,
    )
    subject = client.post("/api/v1/admin/subjects", json={"code": "MATHS", "name": "Mathmatiques"}, headers=headers)
    assert class_group.status_code == 201, class_group.text
    assert subject.status_code == 201, subject.text
    chapter = client.post(
        "/api/v1/admin/chapters",
        json={"grade_id": grade.json()["id"], "subject_id": subject.json()["id"], "title": "Chapitre de test DEMO"},
        headers=headers,
    )
    assert chapter.status_code == 201, chapter.text
