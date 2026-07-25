from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.auth import ensure_bootstrap_admin
from app.db.migrations import run_migrations
from app.jobs.service import create_job, serialise_job
from app.jobs.types import JobStatus, JobType
from app.main import create_app
from app.tenancy import ensure_bootstrap_tenant


def test_job_creation_is_idempotent():
    run_migrations()
    ensure_bootstrap_admin()
    ensure_bootstrap_tenant()
    first, created = create_job(
        workspace_id=1,
        created_by_user_id=1,
        job_type=JobType.DATASET_AUDIT,
        idempotency_key="same-upload",
        payload={"storage_key": "workspaces/1/uploads/a.csv"},
    )
    second, created_again = create_job(
        workspace_id=1,
        created_by_user_id=1,
        job_type=JobType.DATASET_AUDIT,
        idempotency_key="same-upload",
        payload={"storage_key": "workspaces/1/uploads/a.csv"},
    )
    assert created is True
    assert created_again is False
    assert first.id == second.id
    assert serialise_job(first)["status"] == JobStatus.QUEUED


def test_async_upload_completes_and_is_workspace_scoped():
    with TestClient(create_app()) as client:
        login = client.post("/auth/login", json={"email": "admin@drc.local", "password": "ChangeMe123!"})
        assert login.status_code == 200
        response = client.post(
            "/audits/upload/async",
            files={"file": ("background.csv", b"id,name\n1,Alice\n2,Bob\n", "text/csv")},
        )
        assert response.status_code == 202, response.text
        job_id = response.json()["id"]
        deadline = time.time() + 10
        job = None
        while time.time() < deadline:
            current = client.get(f"/jobs/{job_id}")
            assert current.status_code == 200
            job = current.json()
            if job["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.05)
        assert job is not None
        assert job["status"] == "completed", job
        assert job["progress"] == 100
        assert job["result"]["audit_id"]
        assert client.get("/jobs").status_code == 200
