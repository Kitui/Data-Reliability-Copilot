from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import BackgroundJobRecord
from app.db.session import get_session_factory
from app.jobs.types import JobStatus, JobType


def utcnow() -> datetime:
    return datetime.now(UTC)


def serialise_job(row: BackgroundJobRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "created_by_user_id": row.created_by_user_id,
        "job_type": row.job_type,
        "status": row.status,
        "idempotency_key": row.idempotency_key,
        "progress": row.progress,
        "attempt_count": row.attempt_count,
        "payload": json.loads(row.payload_json or "{}"),
        "result": json.loads(row.result_json) if row.result_json else None,
        "error_message": row.error_message,
        "created_at": row.created_at,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
        "failed_at": row.failed_at,
    }


def create_job(
    *,
    workspace_id: int,
    created_by_user_id: int | None,
    job_type: JobType | str,
    idempotency_key: str,
    payload: dict[str, Any],
) -> tuple[BackgroundJobRecord, bool]:
    Session = get_session_factory()
    with Session() as db:
        existing = db.scalar(
            select(BackgroundJobRecord).where(
                BackgroundJobRecord.workspace_id == workspace_id,
                BackgroundJobRecord.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing, False
        row = BackgroundJobRecord(
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            job_type=str(job_type),
            status=JobStatus.QUEUED,
            idempotency_key=idempotency_key,
            progress=0,
            attempt_count=0,
            payload_json=json.dumps(payload),
            created_at=utcnow(),
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(
                select(BackgroundJobRecord).where(
                    BackgroundJobRecord.workspace_id == workspace_id,
                    BackgroundJobRecord.idempotency_key == idempotency_key,
                )
            )
            if existing is None:
                raise
            return existing, False
        db.refresh(row)
        return row, True


def get_job(job_id: int, workspace_id: int | None = None) -> BackgroundJobRecord | None:
    Session = get_session_factory()
    with Session() as db:
        stmt = select(BackgroundJobRecord).where(BackgroundJobRecord.id == job_id)
        if workspace_id is not None:
            stmt = stmt.where(BackgroundJobRecord.workspace_id == workspace_id)
        return db.scalar(stmt)


def list_jobs(workspace_id: int, *, limit: int = 50) -> list[BackgroundJobRecord]:
    Session = get_session_factory()
    with Session() as db:
        return list(
            db.scalars(
                select(BackgroundJobRecord)
                .where(
                    BackgroundJobRecord.workspace_id == workspace_id,
                )
                .order_by(BackgroundJobRecord.created_at.desc())
                .limit(limit)
            ).all()
        )


def update_job(
    job_id: int,
    *,
    status: JobStatus | str | None = None,
    progress: int | None = None,
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
    increment_attempt: bool = False,
) -> BackgroundJobRecord | None:
    Session = get_session_factory()
    with Session() as db:
        row = db.get(BackgroundJobRecord, job_id)
        if row is None:
            return None
        now = utcnow()
        if increment_attempt:
            row.attempt_count += 1
        if status is not None:
            row.status = str(status)
            if status == JobStatus.STARTING and row.started_at is None:
                row.started_at = now
            elif status == JobStatus.COMPLETED:
                row.completed_at = now
                row.failed_at = None
            elif status == JobStatus.FAILED:
                row.failed_at = now
            elif status == JobStatus.CANCELLED:
                row.completed_at = now
        if progress is not None:
            row.progress = max(0, min(100, int(progress)))
        if result is not None:
            row.result_json = json.dumps(result)
        if error_message is not None:
            row.error_message = error_message[:4000]
        db.commit()
        db.refresh(row)
        return row


def cancel_job(job_id: int, workspace_id: int) -> BackgroundJobRecord | None:
    Session = get_session_factory()
    with Session() as db:
        row = db.scalar(
            select(BackgroundJobRecord).where(
                BackgroundJobRecord.id == job_id,
                BackgroundJobRecord.workspace_id == workspace_id,
            )
        )
        if row is None:
            return None
        if row.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            return row
        row.status = JobStatus.CANCELLED
        row.completed_at = utcnow()
        db.commit()
        db.refresh(row)
        return row
