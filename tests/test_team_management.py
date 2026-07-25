from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def login(client: TestClient, email: str | None = None, password: str | None = None) -> None:
    response = client.post(
        "/auth/login",
        json={
            "email": email or get_settings().bootstrap_admin_email,
            "password": password or get_settings().bootstrap_admin_password,
        },
    )
    assert response.status_code == 200


def test_owner_can_invite_and_new_member_can_accept() -> None:
    with TestClient(create_app()) as client:
        login(client)
        invited = client.post(
            "/team/invitations", json={"email": "analyst@example.com", "full_name": "Data Analyst", "role": "analyst"}
        )
        assert invited.status_code == 201
        token = invited.json()["token"]
        client.post("/auth/logout")
        accepted = client.post("/team/invitations/accept", json={"token": token, "password": "StrongPass123!"})
        assert accepted.status_code == 201
        login(client, "analyst@example.com", "StrongPass123!")
        me = client.get("/auth/me").json()["user"]
        assert me["membership_role"] == "analyst"


def test_member_listing_and_role_update() -> None:
    with TestClient(create_app()) as client:
        login(client)
        invited = client.post(
            "/team/invitations", json={"email": "viewer@example.com", "full_name": "Quality Viewer", "role": "viewer"}
        )
        token = invited.json()["token"]
        assert (
            client.post("/team/invitations/accept", json={"token": token, "password": "StrongPass123!"}).status_code
            == 201
        )
        members = client.get("/team/members")
        assert members.status_code == 200
        viewer = next(item for item in members.json() if item["email"] == "viewer@example.com")
        updated = client.patch(f"/team/members/{viewer['membership_id']}/role", json={"role": "analyst"})
        assert updated.status_code == 200
        assert updated.json()["role"] == "analyst"


def test_last_owner_cannot_remove_own_owner_role() -> None:
    with TestClient(create_app()) as client:
        login(client)
        members = client.get("/team/members").json()
        owner = next(item for item in members if item["email"] == get_settings().bootstrap_admin_email)
        response = client.patch(f"/team/members/{owner['membership_id']}/role", json={"role": "admin"})
        assert response.status_code == 409


def test_analyst_cannot_create_invitation() -> None:
    with TestClient(create_app()) as client:
        login(client)
        invited = client.post(
            "/team/invitations",
            json={"email": "limited@example.com", "full_name": "Limited Analyst", "role": "analyst"},
        )
        token = invited.json()["token"]
        client.post("/team/invitations/accept", json={"token": token, "password": "StrongPass123!"})
        client.post("/auth/logout")
        login(client, "limited@example.com", "StrongPass123!")
        denied = client.post(
            "/team/invitations", json={"email": "other@example.com", "full_name": "Other User", "role": "viewer"}
        )
        assert denied.status_code == 403


def test_local_development_email_can_be_invited() -> None:
    from app.api.routes.team import InvitationCreate

    payload = InvitationCreate(email="analyst@drc.local", full_name="Test Analyst", role="analyst")
    assert payload.email == "analyst@drc.local"


def test_invitation_ui_formats_validation_errors_and_copy_link() -> None:
    from pathlib import Path

    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "responseErrorMessage(payload, response.status)" in script
    assert "data-copy-invitation-link" in script
    assert "navigator.clipboard.writeText(url)" in script
