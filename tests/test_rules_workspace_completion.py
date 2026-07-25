from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def login(client: TestClient):
    response = client.post("/auth/login", json={"email": "admin@drc.local", "password": "ChangeMe123!"})
    assert response.status_code == 200


def create_rule(client: TestClient, name: str = "Required customer email") -> int:
    response = client.post(
        "/quality-rules",
        json={
            "name": name,
            "description": "Email is required",
            "rule_type": "required",
            "scope": "column",
            "column_name": "email",
            "category": "completeness",
            "severity": "high",
            "parameters": {},
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_contract_generation_versioning_and_validation():
    with TestClient(create_app()) as client:
        login(client)
        audit = client.post("/audits/sample")
        assert audit.status_code == 200
        dataset = client.get("/datasets").json()[0]
        generated = client.post(f"/quality-rules/contracts/generate/{dataset['id']}")
        assert generated.status_code == 201
        contract = generated.json()
        assert contract["version"] == 1
        assert contract["dataset_name"] == dataset["name"]
        validated = client.post(f"/quality-rules/contracts/{contract['id']}/validate")
        assert validated.status_code == 200
        assert validated.json()["validation_status"] in {"passed", "failed"}
        updated = client.patch(
            f"/quality-rules/contracts/{contract['id']}",
            json={
                "dataset_id": dataset["id"],
                "name": contract["name"],
                "description": "Second version",
                "status": "published",
                "contract": contract["contract"],
            },
        )
        assert updated.status_code == 201
        assert updated.json()["version"] == 2
        versions = client.get(f"/quality-rules/contracts/{updated.json()['id']}/versions")
        assert versions.status_code == 200
        assert [item["version"] for item in versions.json()] == [2, 1]


def test_bulk_assignments_and_execution_history_export():
    with TestClient(create_app()) as client:
        login(client)
        client.post("/audits/sample")
        dataset = client.get("/datasets").json()[0]
        first = create_rule(client, "Required email")
        second = create_rule(client, "Required customer id")
        bulk = client.post(
            "/quality-rules/assignments/bulk",
            json={"rule_ids": [first, second], "dataset_ids": [dataset["id"]], "action": "assign"},
        )
        assert bulk.status_code == 200
        assert bulk.json()["changed"] == 2
        rerun = client.post("/audits/sample")
        assert rerun.status_code == 200
        history = client.get("/quality-rules/executions?outcome=failed&page=1&page_size=50")
        assert history.status_code == 200
        assert history.json()["total"] >= 1
        first_item = history.json()["items"][0]
        assert first_item["affected_percentage"] == round(first_item["affected_rate"] * 100, 2)
        exported = client.get("/quality-rules/executions/export.csv")
        assert exported.status_code == 200
        assert "Rule,Dataset,Outcome" in exported.text
        assert "Affected percentage" in exported.text


def test_completed_workspace_contains_chartjs_and_full_tabs():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "executionOutcomeChart" in html and "executionTrendChart" in html
    assert "bulkAssignmentRules" in html and "contractEditor" in html
    assert "new Chart" in js and "renderExecutionCharts" in js


def test_execution_history_formats_fractional_rate_as_percentage():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "(Number(e.affected_rate || 0) * 100).toFixed(2)" in js
    assert "Number(e.affected_rate).toFixed(2)}%" not in js


def test_contract_registry_keeps_one_latest_lineage_per_dataset_and_status_versions():
    with TestClient(create_app()) as client:
        login(client)
        client.post("/audits/sample")
        dataset = client.get("/datasets").json()[0]
        first = client.post(f"/quality-rules/contracts/generate/{dataset['id']}")
        second = client.post(f"/quality-rules/contracts/generate/{dataset['id']}")
        assert first.status_code == 201 and second.status_code == 201
        assert second.json()["contract_key"] == first.json()["contract_key"]
        assert second.json()["version"] == 2
        registry = client.get("/quality-rules/contracts")
        assert registry.status_code == 200
        assert len(registry.json()) == 1
        assert registry.json()[0]["version"] == 2
        published = client.post(
            f"/quality-rules/contracts/{second.json()['id']}/status",
            json={"status": "published"},
        )
        assert published.status_code == 201
        assert published.json()["status"] == "published"
        assert published.json()["version"] == 3
        archived = client.post(
            f"/quality-rules/contracts/{published.json()['id']}/status",
            json={"status": "archived"},
        )
        assert archived.status_code == 201
        assert archived.json()["status"] == "archived"
        versions = client.get(f"/quality-rules/contracts/{archived.json()['id']}/versions").json()
        assert [item["version"] for item in versions] == [4, 3, 2, 1]


def test_contract_generation_uses_in_app_selector_not_browser_prompt():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "contractGeneratorDataset" in html
    assert "openContractGenerator" in js
    assert "prompt('Enter the dataset name" not in js
    assert "transitionContractStatus" in js


def test_contract_validation_uses_latest_version_audit_and_assigned_rule_results():
    with TestClient(create_app()) as client:
        login(client)
        baseline = (
            b"customer_id,email,account_status,lifetime_value_kes,signup_date\n"
            b"1,a@example.com,active,100,2026-01-01\n"
            b"2,b@example.com,inactive,200,2026-01-02\n"
        )
        first = client.post(
            "/audits/upload",
            files={"file": ("customers.csv", baseline, "text/csv")},
            data={"rules_json": ""},
        )
        assert first.status_code == 200
        baseline_audit_id = first.json()["audit_id"]
        dataset = next(item for item in client.get("/datasets").json() if item["name"] == "customers.csv")

        rules = [
            {
                "name": "Approved account status",
                "rule_type": "allowed_values",
                "scope": "column",
                "column_name": "account_status",
                "category": "validity",
                "severity": "high",
                "parameters": {"values": ["active", "inactive", "suspended"]},
                "is_active": True,
            },
            {
                "name": "Non-negative lifetime value",
                "rule_type": "numeric_range",
                "scope": "column",
                "column_name": "lifetime_value_kes",
                "category": "validity",
                "severity": "high",
                "parameters": {"min": 0, "max": None},
                "is_active": True,
            },
        ]
        rule_ids = []
        for payload in rules:
            response = client.post("/quality-rules", json=payload)
            assert response.status_code == 201
            rule_ids.append(response.json()["id"])
        assigned = client.post(
            "/quality-rules/assignments/bulk",
            json={
                "rule_ids": rule_ids,
                "dataset_ids": [dataset["id"]],
                "action": "assign",
            },
        )
        assert assigned.status_code == 200

        generated = client.post(f"/quality-rules/contracts/generate/{dataset['id']}")
        assert generated.status_code == 201
        contract = generated.json()

        degraded = (
            b"customer_id,email,account_status,lifetime_value_kes,signup_date\n"
            b"1,a@example.com,pending,-2500,2026-01-01\n"
            b"2,b@example.com,active,200,2026-01-02\n"
        )
        imported = client.post(
            f"/datasets/{dataset['id']}/versions/import",
            files={"file": ("customers_v2.csv", degraded, "text/csv")},
        )
        assert imported.status_code == 201
        latest_audit_id = imported.json()["audit_id"]
        assert latest_audit_id != baseline_audit_id

        validated = client.post(f"/quality-rules/contracts/{contract['id']}/validate")
        assert validated.status_code == 200
        body = validated.json()
        assert body["validation_status"] == "failed"
        assert body["source_audit_id"] == latest_audit_id
        assert body["validation"]["audit_id"] == latest_audit_id
        assert body["validation"]["dataset_version"] == 2
        assert body["validation"]["violation_count"] == 2
        assert {item["rule_type"] for item in body["validation"]["violations"]} == {"allowed_values", "numeric_range"}
