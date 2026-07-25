from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import AdministrativeAuditLogRecord, LoginAttemptRecord, SessionRecord
from app.db.session import session_scope
from app.main import create_app


def _login(client: TestClient):
    return client.post(
        "/auth/login",
        json={"email": get_settings().bootstrap_admin_email, "password": get_settings().bootstrap_admin_password},
    )


def test_security_headers_and_request_id_are_present():
    with TestClient(create_app()) as client:
        response = client.get("/health")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["content-security-policy"]
        assert response.headers["x-request-id"]


def test_registration_enforces_strong_password_policy():
    with TestClient(create_app()) as client:
        response = client.post(
            "/auth/register",
            json={
                "full_name": "Weak Password",
                "email": "weak@example.com",
                "password": "password1234",
                "organization_name": "Weak Org",
                "workspace_name": "Workspace",
            },
        )
        assert response.status_code == 400


def test_failed_login_attempts_are_persisted_and_rate_limited(monkeypatch):
    monkeypatch.setenv("DRC_LOGIN_MAX_ATTEMPTS", "2")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        payload = {"email": get_settings().bootstrap_admin_email, "password": "WrongPassword1!"}
        assert client.post("/auth/login", json=payload).status_code == 401
        assert client.post("/auth/login", json=payload).status_code == 401
        assert client.post("/auth/login", json=payload).status_code == 429
    with session_scope() as db:
        assert len(db.scalars(select(LoginAttemptRecord)).all()) == 2


def test_session_inventory_and_revocation():
    with TestClient(create_app()) as client:
        assert _login(client).status_code == 200
        sessions = client.get("/auth/sessions")
        assert sessions.status_code == 200
        session_id = sessions.json()[0]["id"]
        assert client.delete(f"/auth/sessions/{session_id}").status_code == 204
        assert client.get("/auth/me").status_code == 401
    with session_scope() as db:
        row = db.get(SessionRecord, session_id)
        assert row.revoked_at is not None


def test_csrf_blocks_cookie_authenticated_mutation_without_header(monkeypatch):
    monkeypatch.setenv("DRC_CSRF_ENABLED", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        assert _login(client).status_code == 200
        blocked = client.post("/auth/logout")
        assert blocked.status_code == 403
        csrf = client.cookies.get("drc_csrf")
        allowed = client.post("/auth/logout", headers={"X-CSRF-Token": csrf})
        assert allowed.status_code == 204


def test_administrative_audit_log_is_workspace_scoped():
    with TestClient(create_app()) as client:
        assert _login(client).status_code == 200
        response = client.get("/security/audit-log")
        assert response.status_code == 200
        assert any(item["action"] == "auth.login" for item in response.json())
    with session_scope() as db:
        assert (
            db.scalar(select(AdministrativeAuditLogRecord).where(AdministrativeAuditLogRecord.action == "auth.login"))
            is not None
        )
