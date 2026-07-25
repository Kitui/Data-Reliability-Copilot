from pathlib import Path
from fastapi.testclient import TestClient
from app.core.config import get_settings
from app.main import create_app


def login(client: TestClient) -> None:
    response = client.post("/auth/login", json={"email": get_settings().bootstrap_admin_email, "password": get_settings().bootstrap_admin_password})
    assert response.status_code == 200


def test_bootstrap_workspace_is_available() -> None:
    with TestClient(create_app()) as client:
        login(client)
        response = client.get("/workspaces")
        assert response.status_code == 200
        assert response.json()[0]["name"] == "Reliability Operations"
        assert response.json()[0]["active"] is True


def test_owner_can_create_and_activate_workspace_with_isolated_audits() -> None:
    with TestClient(create_app()) as client:
        login(client)
        original = client.post("/audits/sample")
        assert original.status_code == 200
        original_id = original.json()["audit_id"]
        created = client.post("/workspaces", json={"name": "Finance Quality", "description": "Finance controls"})
        assert created.status_code == 200
        workspace_id = created.json()["id"]
        assert client.post(f"/workspaces/{workspace_id}/activate").status_code == 200
        assert client.get("/audits").json() == []
        assert client.get(f"/audits/{original_id}").status_code == 404
        second = client.post("/audits/sample")
        assert second.status_code == 200
        assert len(client.get("/audits").json()) == 1


def test_unauthenticated_workspace_access_is_rejected() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/workspaces").status_code == 401


def test_workspace_creation_controls_are_exposed_in_ui() -> None:
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'id="createWorkspaceButton"' in html
    assert 'id="workspaceCreateForm"' in html
    assert 'async function createWorkspace' in script
    assert 'Create and activate' in html


def test_all_audit_resources_are_isolated_after_workspace_switch() -> None:
    with TestClient(create_app()) as client:
        login(client)
        created_audit = client.post('/audits/sample')
        assert created_audit.status_code == 200
        payload = created_audit.json()
        audit_id = payload['audit_id']
        issue_id = payload['issues'][0]['id']

        created_workspace = client.post('/workspaces', json={'name': 'Isolated Operations', 'description': 'Isolation verification'})
        assert created_workspace.status_code == 200
        assert client.post(f"/workspaces/{created_workspace.json()['id']}/activate").status_code == 200

        protected_reads = [
            f'/audits/{audit_id}',
            f'/audits/{audit_id}/issues',
            f'/audits/{audit_id}/issues/{issue_id}/lifecycle',
            f'/audits/{audit_id}/score-breakdown',
            f'/audits/{audit_id}/report',
            f'/audits/{audit_id}/report.md',
            f'/audits/{audit_id}/report.html',
            f'/audits/{audit_id}/remediation',
            f'/audits/{audit_id}/contract',
            f'/audits/{audit_id}/ml-readiness',
        ]
        for endpoint in protected_reads:
            assert client.get(endpoint).status_code == 404, endpoint

        assert client.post(f'/audits/{audit_id}/rerun').status_code == 404
        assert client.post(f'/audits/{audit_id}/score/recalculate', json={}).status_code == 404
        assert client.post(f'/audits/{audit_id}/issues/{issue_id}/comments', json={'body': 'cross-workspace attempt'}).status_code == 404
        assert client.patch(f'/audits/{audit_id}/issues/{issue_id}', json={'status': 'triaged'}).status_code == 404
        assert client.post(f'/audits/{audit_id}/issues/{issue_id}/apply-recommendation').status_code == 404


def test_workspace_switch_clears_stale_audit_context_in_frontend() -> None:
    script = Path('app/static/app.js').read_text(encoding='utf-8')
    assert 'function clearWorkspaceScopedState()' in script
    assert 'function clearWorkspaceAuditUrl()' in script
    assert 'That audit is not available in the active workspace.' in script
    assert 'if (!response.ok)' in script[script.index('async function openAudit'):script.index('function renderAudit')]
