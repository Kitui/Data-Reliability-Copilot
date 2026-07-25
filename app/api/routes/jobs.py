from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.auth_dependencies import require_user
from app.jobs.runtime import get_dispatcher
from app.jobs.service import cancel_job, get_job, list_jobs, serialise_job, update_job
from app.jobs.types import JobStatus

router = APIRouter(prefix="/jobs", tags=["Background Jobs"])


@router.get("")
def jobs(limit: int = Query(default=25, ge=1, le=100), user: dict[str, object] = Depends(require_user)):
    return [serialise_job(row) for row in list_jobs(int(user["workspace"]["id"]), limit=limit)]


@router.get("/{job_id}")
def job_detail(job_id: int, user: dict[str, object] = Depends(require_user)):
    row = get_job(job_id, int(user["workspace"]["id"]))
    if row is None:
        raise HTTPException(status_code=404, detail="Background job not found.")
    return serialise_job(row)


@router.post("/{job_id}/cancel")
def cancel(job_id: int, user: dict[str, object] = Depends(require_user)):
    row = cancel_job(job_id, int(user["workspace"]["id"]))
    if row is None:
        raise HTTPException(status_code=404, detail="Background job not found.")
    return serialise_job(row)


@router.post("/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry(job_id: int, user: dict[str, object] = Depends(require_user)):
    row = get_job(job_id, int(user["workspace"]["id"]))
    if row is None:
        raise HTTPException(status_code=404, detail="Background job not found.")
    if row.status not in {JobStatus.FAILED, JobStatus.CANCELLED}:
        raise HTTPException(status_code=409, detail="Only failed or cancelled jobs can be retried.")
    row = update_job(job_id, status=JobStatus.QUEUED, progress=0, error_message="")
    get_dispatcher().enqueue(job_id, idempotency_key=row.idempotency_key)
    return serialise_job(row)
