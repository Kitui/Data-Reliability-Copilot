from __future__ import annotations

from pathlib import Path
import pandas as pd
from fastapi.testclient import TestClient

from app.auditor import audit_dataframe
from app.main import create_app
from app.privacy import classify_sensitive_column, scan_dataframe


def login(client: TestClient) -> None:
    response = client.post("/auth/login", json={"email": "admin@drc.local", "password": "ChangeMe123!"})
    assert response.status_code == 200


def test_privacy_detector_classifies_common_sensitive_columns() -> None:
    frame = pd.DataFrame({
        "full_name": ["Amina Kamau", "Brian Otieno"],
        "email": ["amina@example.com", "brian@example.com"],
        "phone_number": ["+254712345678", "+254798765432"],
        "ordinary_metric": [10, 20],
    })
    scan = scan_dataframe(frame)
    by_column = {item["column"]: item for item in scan["findings"]}
    assert by_column["email"]["classification"] == "email"
    assert by_column["phone_number"]["sensitivity"] == "high"
    assert by_column["full_name"]["classification"] == "person_name"
    assert "ordinary_metric" not in by_column


def test_payment_card_uses_critical_sensitivity() -> None:
    signal = classify_sensitive_column("card_number", pd.Series(["4111111111111111", "4012888888881881"]))
    assert signal is not None
    assert signal.classification == "payment_card"
    assert signal.sensitivity == "critical"


def test_audit_generates_column_specific_privacy_findings() -> None:
    frame = pd.DataFrame({
        "email": ["one@example.com", "two@example.com"],
        "city": ["Nairobi", "Kisumu"],
    })
    audit = audit_dataframe(frame, "privacy.csv")
    privacy = [issue for issue in audit.issues if issue.category == "privacy"]
    assert privacy
    assert privacy[0].columns == ["email"]
    assert audit.profile.sensitive_column_count == 1
    assert audit.profile.columns[0].masking_recommendation


def test_privacy_endpoint_returns_latest_profile() -> None:
    with TestClient(create_app()) as client:
        login(client)
        files = {"file": ("privacy.csv", b"email,amount\none@example.com,10\ntwo@example.com,20\n", "text/csv")}
        response = client.post("/audits/upload", files=files)
        assert response.status_code == 200
        datasets = client.get("/datasets").json()
        privacy = client.get(f"/datasets/{datasets[0]['id']}/privacy")
        assert privacy.status_code == 200
        payload = privacy.json()
        assert payload["available"] is True
        assert payload["sensitive_column_count"] >= 1
        assert payload["findings"][0]["classification"] == "email"


def test_privacy_recommendation_requires_recorded_control_and_evidence() -> None:
    with TestClient(create_app()) as client:
        login(client)
        files = {
            "file": (
                "privacy-controls.csv",
                b"full_name,email,phone_number,customer_id\nAmina Kamau,amina@example.com,+254712345678,CUST-001\nBrian Otieno,brian@example.com,+254798765432,CUST-002\n",
                "text/csv",
            )
        }
        audit_response = client.post("/audits/upload", files=files)
        assert audit_response.status_code == 200
        audit = audit_response.json()
        issue = next(item for item in audit["issues"] if item["category"] == "privacy")

        blocked = client.post(f"/audits/{audit['audit_id']}/issues/{issue['id']}/apply-recommendation")
        assert blocked.status_code == 409
        assert "privacy control" in blocked.json()["detail"].lower()

        recorded = client.patch(
            f"/audits/{audit['audit_id']}/issues/{issue['id']}",
            json={
                "resolution_note": "Tokenized email and customer identifiers and restricted raw phone access.",
                "resolution_evidence": "Validation job privacy-control-001 passed; access policy ticket GOV-42.",
            },
        )
        assert recorded.status_code == 200

        applied = client.post(f"/audits/{audit['audit_id']}/issues/{issue['id']}/apply-recommendation")
        assert applied.status_code == 200
        fixed_issue = next(item for item in applied.json()["audit"]["issues"] if item["id"] == issue["id"])
        assert fixed_issue["status"] == "fixed"
        assert "Tokenized email" in fixed_issue["resolution_note"]
        assert "privacy-control-001" in fixed_issue["resolution_evidence"]


def test_privacy_intelligence_ui_renders_per_column_details() -> None:
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    styles = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert "function renderPrivacyIntelligenceV2" in script
    assert "Privacy intelligence" in script
    assert "Confidence" in script
    assert "Why it was detected" in script
    assert "Protection guidance" in script
    assert "Apply Privacy Control" in script
    assert ".privacy-intelligence-panel" in styles
