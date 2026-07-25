from pathlib import Path

from fastapi.testclient import TestClient
from app.main import create_app


def test_feature_ten_audit_workspace_structure():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    styles = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert 'id="auditV2Dashboard"' in html
    assert 'id="auditV2IssueBody"' in html
    assert 'id="auditDatasetSelect"' in html
    assert 'function renderAuditWorkspaceV2' in script
    assert 'function compareCurrentWithPreviousV2' in script
    assert '.audit-kpi-grid' in styles


def test_feature_ten_document_exists():
    document = Path("documents/FEATURE_10_AUDIT_WORKSPACE_OVERHAUL.md")
    assert document.is_file()
    content = document.read_text(encoding="utf-8")
    assert "## Issue Intelligence" in content
    assert "## API and Backend Support" in content


def test_apply_recommendation_resolves_issue_and_recalculates_score():
    with TestClient(create_app()) as client:
        response = client.post('/auth/login', json={'email': 'admin@drc.local', 'password': 'ChangeMe123!'})
        assert response.status_code == 200
        audit_response = client.post('/audits/sample')
        assert audit_response.status_code == 200
        audit = audit_response.json()
        issue = next(item for item in audit['issues'] if item['status'] == 'open')
        previous_score = audit['score']['overall']

        applied = client.post(f"/audits/{audit['audit_id']}/issues/{issue['id']}/apply-recommendation")
        assert applied.status_code == 200
        payload = applied.json()
        assert payload['status'] == 'applied'
        assert payload['updated_score'] >= previous_score
        updated_issue = next(item for item in payload['audit']['issues'] if item['id'] == issue['id'])
        assert updated_issue['status'] == 'fixed'
        assert updated_issue['affected_rows'] == 0
        assert updated_issue['affected_rate'] == 0


def test_selected_audit_can_be_rerun_from_persisted_source() -> None:
    from fastapi.testclient import TestClient
    from app.core.config import get_settings
    from app.main import create_app

    with TestClient(create_app()) as client:
        login = client.post("/auth/login", json={
            "email": get_settings().bootstrap_admin_email,
            "password": get_settings().bootstrap_admin_password,
        })
        assert login.status_code == 200
        first = client.post("/audits/sample")
        assert first.status_code == 200
        rerun = client.post(f"/audits/{first.json()['audit_id']}/rerun")
        assert rerun.status_code == 200
        assert rerun.json()["dataset_name"] == first.json()["dataset_name"]
        assert rerun.json()["audit_id"] != first.json()["audit_id"]
        assert len(client.get("/audits").json()) == 2


def test_uploaded_dataset_rerun_creates_new_selected_run() -> None:
    from app.core.config import get_settings

    csv_bytes = b"customer_id,email,age\nC1,valid@example.com,30\nC2,bad-email,150\n"
    with TestClient(create_app()) as client:
        login = client.post("/auth/login", json={
            "email": get_settings().bootstrap_admin_email,
            "password": get_settings().bootstrap_admin_password,
        })
        assert login.status_code == 200
        first = client.post(
            "/audits/upload",
            files={"file": ("rerun_customers.csv", csv_bytes, "text/csv")},
        )
        assert first.status_code == 200
        first_payload = first.json()

        rerun = client.post(f"/audits/{first_payload['audit_id']}/rerun")
        assert rerun.status_code == 200
        rerun_payload = rerun.json()
        assert rerun_payload["audit_id"] != first_payload["audit_id"]
        assert rerun_payload["dataset_name"] == "rerun_customers.csv"

        history = client.get("/audits").json()
        dataset_runs = [item for item in history if item["dataset_name"] == "rerun_customers.csv"]
        assert len(dataset_runs) == 2
        assert dataset_runs[0]["audit_id"] == rerun_payload["audit_id"]


def test_rerun_frontend_explicitly_loads_new_audit_context() -> None:
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "const payload = await runAudit(" in script
    assert "await openAudit(payload.audit_id);" in script
    assert "auditV2.run.value = payload.audit_id" in script
    assert "url.searchParams.set('audit', payload.audit_id)" in script
