from fastapi.testclient import TestClient

from app.main import create_app


def login(client: TestClient):
    response = client.post("/auth/login", json={"email": "admin@drc.local", "password": "ChangeMe123!"})
    assert response.status_code == 200


def test_issue_lifecycle_updates_comment_and_history():
    with TestClient(create_app()) as client:
        login(client)
        audit = client.post("/audits/sample").json()
        issue = audit["issues"][0]
        update = client.patch(
            f"/audits/{audit['audit_id']}/issues/{issue['id']}",
            json={
                "status": "in_progress",
                "severity": "high",
                "owner": "Data Steward",
                "due_date": "2026-08-01",
                "resolution_note": "Investigating source-system mapping.",
                "resolution_evidence": "Ticket DQ-104 opened.",
            },
        )
        assert update.status_code == 200
        changed = next(item for item in update.json()["issues"] if item["id"] == issue["id"])
        assert changed["status"] == "in_progress"
        assert changed["severity"] == "high"
        assert changed["owner"] == "Data Steward"
        assert changed["due_date"] == "2026-08-01"

        comment = client.post(
            f"/audits/{audit['audit_id']}/issues/{issue['id']}/comments",
            json={"body": "Confirmed the issue with the source-system owner."},
        )
        assert comment.status_code == 200
        assert any(item["action"] == "comment_added" for item in comment.json()["activities"])

        lifecycle = client.get(f"/audits/{audit['audit_id']}/issues/{issue['id']}/lifecycle")
        assert lifecycle.status_code == 200
        actions = lifecycle.json()["activities"]
        assert len(actions) >= 6
        assert any(item["field_name"] == "status" for item in actions)


def test_resolving_issue_requires_note_and_improves_score():
    with TestClient(create_app()) as client:
        login(client)
        audit = client.post("/audits/sample").json()
        issue = audit["issues"][0]
        rejected = client.patch(f"/audits/{audit['audit_id']}/issues/{issue['id']}", json={"status": "resolved"})
        assert rejected.status_code == 400
        resolved = client.patch(
            f"/audits/{audit['audit_id']}/issues/{issue['id']}",
            json={"status": "resolved", "resolution_note": "Corrected and revalidated."},
        )
        assert resolved.status_code == 200
        updated = next(item for item in resolved.json()["issues"] if item["id"] == issue["id"])
        assert updated["status"] == "resolved"
        assert resolved.json()["score"]["overall"] >= audit["score"]["overall"]
