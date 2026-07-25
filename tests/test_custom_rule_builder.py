from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def login(client: TestClient) -> None:
    response = client.post("/auth/login", json={"email": "admin@drc.local", "password": "ChangeMe123!"})
    assert response.status_code == 200


def test_builder_context_and_rule_test_preview() -> None:
    with TestClient(create_app()) as client:
        login(client)
        audit = client.post("/audits/sample")
        assert audit.status_code == 200
        dataset = client.get("/datasets").json()[0]

        context = client.get(f"/quality-rules/builder/context/{dataset['id']}")
        assert context.status_code == 200
        assert any(column["name"] == "email" for column in context.json()["columns"])

        preview = client.post(
            "/quality-rules/builder/test",
            json={
                "dataset_id": dataset["id"],
                "rule": {
                    "name": "Customer email format",
                    "rule_type": "email",
                    "scope": "column",
                    "column_name": "email",
                    "category": "validity",
                    "severity": "high",
                    "parameters": {},
                    "is_active": True,
                },
            },
        )
        assert preview.status_code == 200
        payload = preview.json()
        assert payload["outcome"] in {"passed", "failed"}
        assert payload["total_rows"] > 0
        assert 0 <= payload["affected_percentage"] <= 100
        assert "estimated_score_impact" in payload


def test_custom_rule_builder_ui_is_wired() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        assert "Custom Rule Builder" in html
        assert "ruleBuilderDataset" in html
        assert "testRuleButton" in html
        assert "ruleTestResult" in html


def test_rule_builder_refreshes_registered_datasets_when_editor_opens() -> None:
    script = (Path(__file__).resolve().parents[1] / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert "async function refreshRuleBuilderDatasets" in script
    assert "fetch('/datasets')" in script
    assert "await refreshRuleBuilderDatasets" in script
    assert "Loading datasets…" in script or "Loading datasets\\u2026" in script


def test_rule_builder_allows_manual_column_without_dataset():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'id="ruleColumn" list="ruleColumnOptions"' in html
    assert "Enter or select a target column for this column-level rule." in js
    assert "toggle.disabled=!datasetSelected" in js


def test_rule_save_button_uses_direct_click_binding() -> None:
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'id="saveRuleButton"' in html
    assert 'type="button" id="saveRuleButton" onclick="saveRule(event)"' in html
    assert "const saveButton=document.querySelector('#saveRuleButton');" in script
