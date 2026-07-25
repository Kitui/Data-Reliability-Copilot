from fastapi.testclient import TestClient

from app.main import create_app


def login(client: TestClient) -> None:
    response = client.post("/auth/login", json={"email": "admin@drc.local", "password": "ChangeMe123!"})
    assert response.status_code == 200


def sample_payload(name: str = "BigQuery - Analytics") -> dict:
    return {
        "name": name,
        "source_type": "BigQuery",
        "host_project": "analytics-prod-01",
        "configuration": {"project_id": "analytics-prod-01", "dataset": "analytics", "dataset_name": "analytics"},
        "credential_hint": None,
    }


def test_connector_crud_test_sync_and_delete() -> None:
    with TestClient(create_app()) as client:
        login(client)
        created = client.post("/connectors", json=sample_payload())
        assert created.status_code == 200
        connector = created.json()
        assert connector["source_type"] == "BigQuery"
        dashboard = client.get("/connectors").json()
        assert dashboard["metrics"]["total"] == 1
        tested = client.post(f"/connectors/{connector['id']}/test")
        assert tested.status_code == 200
        assert tested.json()["status"] == "active"
        synced = client.post(f"/connectors/{connector['id']}/sync")
        assert synced.status_code == 200
        assert synced.json()["status"] == "completed"
        assert client.delete(f"/connectors/{connector['id']}").status_code == 200


def test_connectors_are_workspace_scoped() -> None:
    with TestClient(create_app()) as client:
        login(client)
        assert client.post("/connectors", json=sample_payload("Workspace A Connector")).status_code == 200
        workspace = client.post("/workspaces", json={"name": "Connector Isolation", "description": "test"})
        assert workspace.status_code == 200
        workspace_id = workspace.json()["id"]
        assert client.post(f"/workspaces/{workspace_id}/activate").status_code == 200
        payload = client.get("/connectors").json()
        assert payload["metrics"]["total"] == 0


def test_connectors_ui_uses_svg_icons_and_alert_refinements() -> None:
    with TestClient(create_app()) as client:
        html = client.get("/").text
        css = client.get("/static/styles.css").text
        js = client.get("/static/app.js").text
        assert 'id="connectorsPage"' in html
        assert 'id="connectorsNavButton"' in html
        assert "connectorIcons" in js
        assert "Feature 22: Connectors workspace and alert density refinements" in css
        assert "font-style:normal!important" in css
        assert "grid-template-columns:minmax(0,2.35fr)" in css
