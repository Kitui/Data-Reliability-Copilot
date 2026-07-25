from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import ensure_bootstrap_admin
from app.core.config import get_settings
from app.db.migrations import run_migrations
from app.db.models import UserRecord
from app.db.session import session_scope
from app.main import create_app


def test_bootstrap_admin_is_created_with_hashed_password() -> None:
    run_migrations()
    ensure_bootstrap_admin()
    with session_scope() as db:
        user = db.scalar(select(UserRecord).where(UserRecord.email == get_settings().bootstrap_admin_email))
        assert user is not None
        assert user.password_hash.startswith("pbkdf2_sha256$")
        assert get_settings().bootstrap_admin_password not in user.password_hash


def test_login_session_and_logout_flow() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/auth/me").status_code == 401
        response = client.post(
            "/auth/login",
            json={
                "email": get_settings().bootstrap_admin_email,
                "password": get_settings().bootstrap_admin_password,
            },
        )
        assert response.status_code == 200
        assert response.json()["user"]["role"] == "admin"
        assert client.get("/auth/me").status_code == 200
        assert client.post("/auth/logout").status_code == 204
        assert client.get("/auth/me").status_code == 401


def test_audit_routes_require_authentication() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/audits").status_code == 401


def test_self_service_registration_creates_owner_tenant_and_session() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/auth/register",
            json={
                "full_name": "Paul Test",
                "email": "paul@example.com",
                "password": "StrongPass123!",
                "organization_name": "Opsyn Labs",
                "workspace_name": "Data Reliability",
            },
        )
        assert response.status_code == 201
        user = response.json()["user"]
        assert user["membership_role"] == "owner"
        assert user["organization"]["name"] == "Opsyn Labs"
        assert user["workspace"]["name"] == "Data Reliability"
        assert client.get("/auth/me").status_code == 200
        with session_scope() as db:
            created = db.scalar(select(UserRecord).where(UserRecord.email == "paul@example.com"))
            assert created is not None
            assert created.password_hash.startswith("pbkdf2_sha256$")


def test_self_service_registration_rejects_duplicate_email() -> None:
    payload = {
        "full_name": "First Owner",
        "email": "owner@example.com",
        "password": "StrongPass123!",
        "organization_name": "First Org",
        "workspace_name": "Reliability Operations",
    }
    with TestClient(create_app()) as client:
        assert client.post("/auth/register", json=payload).status_code == 201
        duplicate = client.post("/auth/register", json={**payload, "organization_name": "Second Org"})
        assert duplicate.status_code == 409
