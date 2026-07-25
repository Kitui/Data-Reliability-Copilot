from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from app.jobs.handlers import HANDLERS
from app.jobs.service import get_job, update_job
from app.jobs.types import JobStatus, JobType
from app.jobs.worker import JobContext, JobDispatcher

logger = logging.getLogger(__name__)


class LocalThreadDispatcher(JobDispatcher):
    """In-process development dispatcher. Production can replace this with Cloud Tasks."""

    def __init__(self, max_workers: int = 2) -> None:
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="drc-job")

    def enqueue(self, job_id: int, *, idempotency_key: str) -> None:
        _ = idempotency_key
        self.executor.submit(run_job, job_id)


_dispatcher: LocalThreadDispatcher | None = None
_lock = Lock()


def get_dispatcher() -> JobDispatcher:
    global _dispatcher
    with _lock:
        if _dispatcher is None:
            _dispatcher = LocalThreadDispatcher()
        return _dispatcher


def run_job(job_id: int) -> None:
    row = get_job(job_id)
    if row is None or row.status == JobStatus.CANCELLED:
        return
    update_job(job_id, status=JobStatus.STARTING, progress=5, increment_attempt=True, error_message="")
    try:
        row = get_job(job_id)
        if row is None or row.status == JobStatus.CANCELLED:
            return
        payload = json.loads(row.payload_json or "{}")
        update_job(job_id, status=JobStatus.VALIDATING, progress=15)
        handler = HANDLERS.get(row.job_type)
        if handler is None:
            raise RuntimeError(f"No background handler is registered for {row.job_type}.")
        update_job(job_id, status=JobStatus.PROCESSING, progress=35)
        context = JobContext(job_id=row.id, workspace_id=row.workspace_id, job_type=JobType(row.job_type), payload=payload)
        result = handler.execute(context)
        current = get_job(job_id)
        if current is not None and current.status == JobStatus.CANCELLED:
            return
        update_job(job_id, status=JobStatus.COMPLETED, progress=100, result=result)
    except Exception as exc:
        logger.exception("Background job %s failed", job_id)
        update_job(job_id, status=JobStatus.FAILED, progress=100, error_message=str(exc))
