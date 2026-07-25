from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def login(client: TestClient):
    response = client.post(
        "/auth/login",
        json={"email": get_settings().bootstrap_admin_email, "password": get_settings().bootstrap_admin_password},
    )
    assert response.status_code == 200


def test_dataset_registry_crud_and_summary():
    with TestClient(create_app()) as client:
        login(client)
        created = client.post(
            "/datasets",
            json={
                "name": "orders_master.csv",
                "domain": "Sales",
                "owner_name": "Data Team",
                "environment": "production",
                "source_type": "CSV",
                "labels": ["Sales", "Critical"],
            },
        )
        assert created.status_code == 201
        dataset_id = created.json()["id"]
        assert client.get("/datasets").json()[0]["name"] == "orders_master.csv"
        updated = client.patch(f"/datasets/{dataset_id}", json={"environment": "staging", "labels": ["Sales"]})
        assert updated.status_code == 200
        assert updated.json()["environment"] == "staging"
        summary = client.get("/datasets/summary").json()
        assert summary["registered"] == 1
        assert client.delete(f"/datasets/{dataset_id}").status_code == 204
        assert client.get("/datasets").json() == []


def test_sample_audit_registers_dataset():
    with TestClient(create_app()) as client:
        login(client)
        audit = client.post("/audits/sample")
        assert audit.status_code == 200
        datasets = client.get("/datasets").json()
        assert len(datasets) == 1
        assert datasets[0]["latest_audit_id"] == audit.json()["audit_id"]
        assert datasets[0]["quality_score"] == audit.json()["score"]["overall"]


def test_dataset_registry_is_workspace_scoped():
    with TestClient(create_app()) as client:
        login(client)
        assert client.post("/datasets", json={"name": "private.csv"}).status_code == 201
        created = client.post("/workspaces", json={"name": "Second Workspace"})
        assert client.post(f"/workspaces/{created.json()['id']}/activate").status_code == 200
        assert client.get("/datasets").json() == []


def test_dataset_preview_returns_schema_and_sample_rows():
    with TestClient(create_app()) as client:
        login(client)
        sample = b"customer_id,email,age\n1,a@example.com,30\n2,,41\n"
        uploaded = client.post(
            "/audits/upload", files={"file": ("preview.csv", sample, "text/csv")}, data={"rules_json": ""}
        )
        assert uploaded.status_code == 200
        datasets = client.get("/datasets").json()
        row = next(item for item in datasets if item["name"] == "preview.csv")
        response = client.get(f"/datasets/{row['id']}/preview")
        assert response.status_code == 200
        payload = response.json()
        assert payload["available"] is True
        assert payload["row_count"] == 2
        assert payload["column_count"] == 3
        assert payload["columns"][1]["name"] == "email"
        assert isinstance(payload["rows"], list)


def test_upload_rejects_duplicate_column_names():
    with TestClient(create_app()) as client:
        login(client)
        response = client.post(
            "/audits/upload", files={"file": ("duplicate.csv", b"id,id\n1,2\n", "text/csv")}, data={"rules_json": ""}
        )
        assert response.status_code == 400
        assert "duplicate column names" in response.json()["detail"].lower()


def test_column_intelligence_exposes_risk_and_statistics():
    with TestClient(create_app()) as client:
        login(client)
        sample = b"customer_id,amount,segment\n1,10,A\n2,11,A\n3,12,A\n4,9999,A\n5,,A\n"
        uploaded = client.post(
            "/audits/upload", files={"file": ("intelligence.csv", sample, "text/csv")}, data={"rules_json": ""}
        )
        assert uploaded.status_code == 200
        row = next(item for item in client.get("/datasets").json() if item["name"] == "intelligence.csv")
        preview = client.get(f"/datasets/{row['id']}/preview").json()
        amount = next(column for column in preview["columns"] if column["name"] == "amount")
        segment = next(column for column in preview["columns"] if column["name"] == "segment")
        assert amount["inferred_type"] == "numeric"
        assert amount["outlier_count"] == 1
        assert amount["risk_level"] in {"low", "medium", "high"}
        assert segment["constant"] is True
        assert segment["cardinality"] == "constant"
        intelligence = client.get(f"/datasets/{row['id']}/intelligence")
        assert intelligence.status_code == 200
        assert intelligence.json()["available"] is True
        assert intelligence.json()["column_count"] == 3


def test_dataset_metadata_and_labels_persist():
    with TestClient(create_app()) as client:
        login(client)
        created = client.post("/datasets", json={"name": "metadata.csv", "domain": "General"})
        assert created.status_code == 201
        dataset_id = created.json()["id"]
        updated = client.patch(
            f"/datasets/{dataset_id}",
            json={
                "name": "customer_operations.csv",
                "domain": "Customer Operations",
                "owner_name": "Paul Kitui",
                "environment": "staging",
                "source_type": "CSV Upload",
                "description": "Customer operations reliability dataset.",
                "labels": ["customer-data", "operations"],
            },
        )
        assert updated.status_code == 200
        body = updated.json()
        assert body["name"] == "customer_operations.csv"
        assert body["domain"] == "Customer Operations"
        assert body["labels"] == ["customer-data", "operations"]
        fetched = client.get(f"/datasets/{dataset_id}")
        assert fetched.status_code == 200
        assert fetched.json()["labels"] == ["customer-data", "operations"]
        assert fetched.json()["description"] == "Customer operations reliability dataset."


def test_dataset_frontend_routes_edit_action_to_metadata_editor():
    source = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'if (action === "edit") { openDatasetEditor(row); return; }' in source
    assert "await selectDataset(optimistic.id);" in source


def test_import_new_dataset_version_creates_audit_lineage_and_schema_drift():
    with TestClient(create_app()) as client:
        login(client)
        first = b"customer_id,email,age\n1,a@example.com,30\n2,b@example.com,41\n"
        uploaded = client.post(
            "/audits/upload", files={"file": ("customers.csv", first, "text/csv")}, data={"rules_json": ""}
        )
        assert uploaded.status_code == 200
        dataset = next(item for item in client.get("/datasets").json() if item["name"] == "customers.csv")

        second = b"customer_id,email,age,loyalty_tier\n1,a@example.com,30,gold\n2,b@example.com,41,silver\n"
        imported = client.post(
            f"/datasets/{dataset['id']}/versions/import",
            files={"file": ("customers_v2.csv", second, "text/csv")},
        )
        assert imported.status_code == 201
        assert imported.json()["version"] == 2
        assert imported.json()["dataset_name"] == "customers.csv"

        registry = client.get("/datasets").json()
        lineage = next(item for item in registry if item["id"] == dataset["id"])
        assert lineage["name"] == "customers.csv"
        assert lineage["latest_version"] == 2
        assert lineage["latest_source_filename"] == "customers_v2.csv"
        assert len([item for item in registry if item["name"] == "customers.csv"]) == 1

        versions = client.get(f"/datasets/{dataset['id']}/versions").json()
        assert versions["version_count"] == 2
        assert versions["versions"][-1]["column_count"] == 4

        drift = client.get("/schema-drift").json()
        assert drift["summary"]["total"] >= 1
        assert any(event["drift_type"] == "column_added" for event in drift["events"])


def test_dataset_version_import_is_workspace_scoped():
    with TestClient(create_app()) as client:
        login(client)
        uploaded = client.post(
            "/audits/upload", files={"file": ("scoped.csv", b"id\n1\n", "text/csv")}, data={"rules_json": ""}
        )
        assert uploaded.status_code == 200
        dataset = next(item for item in client.get("/datasets").json() if item["name"] == "scoped.csv")
        second = client.post("/workspaces", json={"name": "Version Isolation"})
        assert second.status_code == 200
        assert client.post(f"/workspaces/{second.json()['id']}/activate").status_code == 200
        response = client.post(
            f"/datasets/{dataset['id']}/versions/import",
            files={"file": ("scoped_v2.csv", b"id,new_col\n1,x\n", "text/csv")},
        )
        assert response.status_code == 404


def test_version_import_returns_verified_automatic_audit_result():
    with TestClient(create_app()) as client:
        login(client)
        uploaded = client.post(
            "/audits/upload", files={"file": ("verified.csv", b"id,value\n1,a\n", "text/csv")}, data={"rules_json": ""}
        )
        assert uploaded.status_code == 200
        dataset = next(item for item in client.get("/datasets").json() if item["name"] == "verified.csv")
        response = client.post(
            f"/datasets/{dataset['id']}/versions/import",
            files={"file": ("verified_v2.csv", b"id,value,new_col\n1,a,x\n", "text/csv")},
        )
        assert response.status_code == 201
        payload = response.json()
        assert payload["audit_status"] == "completed"
        assert payload["audit_id"]
        assert payload["source_filename"] == "verified_v2.csv"
        audit = client.get(f"/audits/{payload['audit_id']}")
        assert audit.status_code == 200
        assert audit.json()["audit_id"] == payload["audit_id"]
        versions = client.get(f"/datasets/{dataset['id']}/versions").json()
        assert versions["versions"][-1]["audit_id"] == payload["audit_id"]
