from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.db.models import AuditScheduleRecord, DatasetRecord, ScheduledAuditRunRecord
from app.db.session import get_session_factory
from app.jobs.runtime import get_dispatcher
from app.jobs.service import create_job, serialise_job
from app.jobs.types import JobType


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _next_occurrence(schedule: AuditScheduleRecord, after: datetime) -> datetime:
    # Import lazily to avoid a route/service import cycle.
    from app.api.routes.schedules import next_occurrence

    return next_occurrence(
        schedule.frequency,
        schedule.hour,
        schedule.minute,
        schedule.day_of_week,
        schedule.day_of_month,
        after,
        schedule.timezone_offset_minutes or 0,
    )


def _create_job_for_run(
    *,
    schedule_id: int,
    run_id: int,
    workspace_id: int,
    user_id: int | None,
    actor_name: str,
    triggered_by: str,
    occurrence_key: str,
) -> dict[str, Any]:
    job, created = create_job(
        workspace_id=workspace_id,
        created_by_user_id=user_id,
        job_type=JobType.SCHEDULED_AUDIT,
        idempotency_key=f"scheduled-audit:{schedule_id}:{occurrence_key}",
        payload={
            "schedule_id": schedule_id,
            "run_id": run_id,
            "actor_name": actor_name,
            "triggered_by": triggered_by,
        },
    )
    Session = get_session_factory()
    with Session() as db:
        run = db.get(ScheduledAuditRunRecord, run_id)
        if run is not None:
            run.background_job_id = job.id
            db.commit()
    if created:
        get_dispatcher().enqueue(job.id, idempotency_key=job.idempotency_key)
    return serialise_job(job)


def queue_manual_run(
    schedule_id: int,
    workspace_id: int,
    actor_name: str,
    user_id: int | None,
) -> dict[str, Any]:
    Session = get_session_factory()
    now = utcnow()
    with Session() as db:
        schedule = db.scalar(
            select(AuditScheduleRecord).where(
                AuditScheduleRecord.id == schedule_id,
                AuditScheduleRecord.workspace_id == workspace_id,
            )
        )
        if schedule is None:
            raise LookupError("Schedule not found.")
        dataset = db.scalar(
            select(DatasetRecord).where(
                DatasetRecord.id == schedule.dataset_id,
                DatasetRecord.workspace_id == workspace_id,
            )
        )
        if dataset is None:
            raise RuntimeError("The scheduled dataset is unavailable.")
        run = ScheduledAuditRunRecord(
            schedule_id=schedule.id,
            workspace_id=workspace_id,
            dataset_id=schedule.dataset_id,
            status="queued",
            triggered_by="manual",
            started_at=now,
        )
        db.add(run)
        schedule.last_status = "queued"
        schedule.last_error = None
        schedule.updated_at = now
        db.commit()
        db.refresh(run)
        run_id = run.id
    return _create_job_for_run(
        schedule_id=schedule_id,
        run_id=run_id,
        workspace_id=workspace_id,
        user_id=user_id,
        actor_name=actor_name,
        triggered_by="manual",
        occurrence_key=f"manual:{run_id}",
    )


def dispatch_due_schedules(*, limit: int = 25, actor_name: str = "Scheduled automation") -> list[dict[str, Any]]:
    """Atomically claim due schedules, advance them, and enqueue background jobs.

    Row locking plus advancing ``next_run_at`` before the transaction commits prevents
    multiple scheduler instances from dispatching the same occurrence.
    """
    Session = get_session_factory()
    now = utcnow()
    claimed: list[dict[str, Any]] = []
    with Session() as db:
        statement = (
            select(AuditScheduleRecord)
            .where(
                AuditScheduleRecord.status == "active",
                AuditScheduleRecord.next_run_at <= now,
            )
            .order_by(AuditScheduleRecord.next_run_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        schedules = list(db.scalars(statement).all())
        for schedule in schedules:
            due_at = ensure_utc(schedule.next_run_at)
            run = ScheduledAuditRunRecord(
                schedule_id=schedule.id,
                workspace_id=schedule.workspace_id,
                dataset_id=schedule.dataset_id,
                status="queued",
                triggered_by="schedule",
                started_at=now,
                scheduled_for=due_at,
            )
            db.add(run)
            schedule.next_run_at = _next_occurrence(schedule, now)
            schedule.last_status = "queued"
            schedule.last_error = None
            schedule.claimed_at = now
            schedule.updated_at = now
            db.flush()
            claimed.append(
                {
                    "schedule_id": schedule.id,
                    "run_id": run.id,
                    "workspace_id": schedule.workspace_id,
                    "occurrence_key": due_at.isoformat(),
                }
            )
        db.commit()

    jobs: list[dict[str, Any]] = []
    for item in claimed:
        try:
            jobs.append(
                _create_job_for_run(
                    schedule_id=item["schedule_id"],
                    run_id=item["run_id"],
                    workspace_id=item["workspace_id"],
                    user_id=None,
                    actor_name=actor_name,
                    triggered_by="schedule",
                    occurrence_key=item["occurrence_key"],
                )
            )
        except Exception as exc:
            with Session() as db:
                run = db.get(ScheduledAuditRunRecord, item["run_id"])
                schedule = db.get(AuditScheduleRecord, item["schedule_id"])
                if run is not None:
                    run.status = "failed"
                    run.completed_at = utcnow()
                    run.error_message = str(exc)[:4000]
                if schedule is not None:
                    schedule.last_status = "failed"
                    schedule.last_error = str(exc)[:4000]
                    schedule.updated_at = utcnow()
                db.commit()
    return jobs
