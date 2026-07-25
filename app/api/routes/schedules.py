from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.auth_dependencies import require_roles, require_user
from app.core.config import get_settings
from app.db.models import AuditRecord, AuditScheduleRecord, DatasetRecord, ScheduledAuditRunRecord
from app.db.session import get_session_factory

router = APIRouter(prefix="/schedules", tags=["Scheduled Audits"])


class ScheduleCreate(BaseModel):
    dataset_id: int
    name: str | None = None
    frequency: str = Field(pattern="^(daily|weekly|monthly)$")
    hour: int = Field(ge=0, le=23)
    minute: int = Field(ge=0, le=59)
    timezone_offset_minutes: int = Field(default=0, ge=-840, le=840)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=28)


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def next_occurrence(
    frequency: str,
    hour: int,
    minute: int,
    day_of_week: int | None,
    day_of_month: int | None,
    after: datetime | None = None,
    timezone_offset_minutes: int = 0,
) -> datetime:
    """Return the next UTC execution time for a wall-clock schedule.

    ``timezone_offset_minutes`` follows JavaScript's ``Date.getTimezoneOffset``
    convention (UTC minus local time). For Nairobi, for example, it is -180.
    """
    now_utc = ensure_utc(after) or utcnow()
    local_tz = timezone(timedelta(minutes=-timezone_offset_minutes))
    now_local = now_utc.astimezone(local_tz)
    candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if frequency == "daily":
        if candidate <= now_local:
            candidate += timedelta(days=1)
    elif frequency == "weekly":
        target = 0 if day_of_week is None else day_of_week
        candidate += timedelta(days=(target - candidate.weekday()) % 7)
        if candidate <= now_local:
            candidate += timedelta(days=7)
    else:
        target_day = day_of_month or 1
        candidate = candidate.replace(day=min(target_day, 28))
        if candidate <= now_local:
            year = candidate.year + (1 if candidate.month == 12 else 0)
            month = 1 if candidate.month == 12 else candidate.month + 1
            candidate = candidate.replace(year=year, month=month, day=min(target_day, 28))
    return candidate.astimezone(UTC)


def serialize_schedule(row: AuditScheduleRecord, dataset: DatasetRecord | None, audit: AuditRecord | None) -> dict:
    return {
        "id": row.id,
        "dataset_id": row.dataset_id,
        "dataset_name": dataset.name if dataset else "Unavailable dataset",
        "source_type": dataset.source_type if dataset else "Unknown",
        "name": row.name,
        "frequency": row.frequency,
        "hour": row.hour,
        "minute": row.minute,
        "timezone_offset_minutes": row.timezone_offset_minutes or 0,
        "day_of_week": row.day_of_week,
        "day_of_month": row.day_of_month,
        "status": row.status,
        "next_run_at": ensure_utc(row.next_run_at),
        "last_run_at": ensure_utc(row.last_run_at),
        "last_status": row.last_status,
        "last_audit_id": row.last_audit_id,
        "last_error": row.last_error,
        "score": audit.score if audit else None,
        "issue_count": audit.issue_count if audit else None,
        "risk_level": audit.risk_level if audit else None,
    }


def process_all_due(actor_name: str = "Scheduled automation") -> int:
    """Compatibility wrapper for dedicated dispatch callers and older integrations."""
    from app.scheduling.service import dispatch_due_schedules

    return len(dispatch_due_schedules(actor_name=actor_name))


@router.post("/dispatch", status_code=http_status.HTTP_202_ACCEPTED)
def dispatch_due(
    x_drc_scheduler_token: str | None = Header(default=None, alias="X-DRC-Scheduler-Token"),
):
    """Claim due schedules and enqueue jobs; intended for Cloud Scheduler or a dedicated cron service."""
    import secrets

    from app.scheduling.service import dispatch_due_schedules

    expected = get_settings().scheduler_token
    if not expected or not x_drc_scheduler_token or not secrets.compare_digest(expected, x_drc_scheduler_token):
        raise HTTPException(401, "Invalid scheduler token.")
    jobs = dispatch_due_schedules()
    return {"dispatched": len(jobs), "jobs": jobs}


@router.get("")
def dashboard(
    timezone_offset_minutes: int | None = Query(default=None, ge=-840, le=840), user: dict = Depends(require_user)
):
    wid = user["workspace"]["id"]
    Session = get_session_factory()
    with Session() as db:
        schedules = list(
            db.scalars(
                select(AuditScheduleRecord)
                .where(AuditScheduleRecord.workspace_id == wid)
                .order_by(AuditScheduleRecord.next_run_at)
            ).all()
        )
        # Upgrade legacy schedules on first load using the browser's actual local
        # timezone. This repairs schedules created before timezone support.
        if timezone_offset_minutes is not None:
            changed = False
            for schedule in schedules:
                if schedule.timezone_offset_minutes is None:
                    schedule.timezone_offset_minutes = timezone_offset_minutes
                    schedule.next_run_at = next_occurrence(
                        schedule.frequency,
                        schedule.hour,
                        schedule.minute,
                        schedule.day_of_week,
                        schedule.day_of_month,
                        timezone_offset_minutes=timezone_offset_minutes,
                    )
                    changed = True
            if changed:
                db.commit()
                schedules = list(
                    db.scalars(
                        select(AuditScheduleRecord)
                        .where(AuditScheduleRecord.workspace_id == wid)
                        .order_by(AuditScheduleRecord.next_run_at)
                    ).all()
                )
        datasets = {x.id: x for x in db.scalars(select(DatasetRecord).where(DatasetRecord.workspace_id == wid)).all()}
        audit_ids = [x.last_audit_id for x in schedules if x.last_audit_id]
        audits = (
            {x.audit_id: x for x in db.scalars(select(AuditRecord).where(AuditRecord.audit_id.in_(audit_ids))).all()}
            if audit_ids
            else {}
        )
        runs = list(
            db.scalars(
                select(ScheduledAuditRunRecord)
                .where(ScheduledAuditRunRecord.workspace_id == wid)
                .order_by(ScheduledAuditRunRecord.started_at.desc())
                .limit(50)
            ).all()
        )
    seven = utcnow() - timedelta(days=7)
    recent = [
        r for r in runs if (r.started_at.replace(tzinfo=UTC) if r.started_at.tzinfo is None else r.started_at) >= seven
    ]
    rows = [serialize_schedule(s, datasets.get(s.dataset_id), audits.get(s.last_audit_id)) for s in schedules]
    upcoming = sorted([r for r in rows if r["status"] == "active"], key=lambda x: x["next_run_at"])[:6]
    run_rows = []
    for r in runs[:12]:
        d = datasets.get(r.dataset_id)
        run_rows.append(
            {
                "id": r.id,
                "dataset_name": d.name if d else "Unavailable dataset",
                "started_at": ensure_utc(r.started_at),
                "completed_at": ensure_utc(r.completed_at),
                "duration_ms": r.duration_ms,
                "status": r.status,
                "score": r.score,
                "issue_count": r.issue_count,
                "triggered_by": r.triggered_by,
                "audit_id": r.audit_id,
                "error_message": r.error_message,
                "background_job_id": r.background_job_id,
                "scheduled_for": ensure_utc(r.scheduled_for),
            }
        )
    return {
        "schedules": rows,
        "upcoming": upcoming,
        "runs": run_rows,
        "metrics": {
            "total": len(rows),
            "active": sum(x["status"] == "active" for x in rows),
            "completed_7d": sum(x.status == "completed" for x in recent),
            "failed_7d": sum(x.status == "failed" for x in recent),
            "next_run_at": upcoming[0]["next_run_at"] if upcoming else None,
        },
    }


@router.post("")
def create(payload: ScheduleCreate, user: dict = Depends(require_roles("owner", "admin"))):
    wid = user["workspace"]["id"]
    Session = get_session_factory()
    now = utcnow()
    with Session() as db:
        dataset = db.scalar(
            select(DatasetRecord).where(DatasetRecord.id == payload.dataset_id, DatasetRecord.workspace_id == wid)
        )
        if not dataset:
            raise HTTPException(404, "Dataset not found.")
        row = AuditScheduleRecord(
            workspace_id=wid,
            dataset_id=dataset.id,
            name=payload.name or f"{dataset.name} audit",
            frequency=payload.frequency,
            hour=payload.hour,
            minute=payload.minute,
            timezone_offset_minutes=payload.timezone_offset_minutes,
            day_of_week=payload.day_of_week,
            day_of_month=payload.day_of_month,
            status="active",
            next_run_at=next_occurrence(
                payload.frequency,
                payload.hour,
                payload.minute,
                payload.day_of_week,
                payload.day_of_month,
                timezone_offset_minutes=payload.timezone_offset_minutes,
            ),
            created_by_user_id=user["id"],
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"id": row.id, "message": "Schedule created."}


@router.post("/{schedule_id}/run", status_code=http_status.HTTP_202_ACCEPTED)
def run_now(schedule_id: int, user: dict = Depends(require_roles("owner", "admin"))):
    from app.scheduling.service import queue_manual_run

    try:
        job = queue_manual_run(
            schedule_id,
            int(user["workspace"]["id"]),
            str(user.get("full_name") or "Workspace team"),
            int(user["id"]),
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"message": "Scheduled audit queued.", "job": job}


@router.patch("/{schedule_id}/status")
def status(schedule_id: int, payload: dict, user: dict = Depends(require_roles("owner", "admin"))):
    requested = payload.get("status")
    if requested not in {"active", "paused"}:
        raise HTTPException(400, "Status must be active or paused.")
    Session = get_session_factory()
    wid = user["workspace"]["id"]
    with Session() as db:
        row = db.scalar(
            select(AuditScheduleRecord).where(
                AuditScheduleRecord.id == schedule_id, AuditScheduleRecord.workspace_id == wid
            )
        )
        if not row:
            raise HTTPException(404, "Schedule not found.")
        row.status = requested
        row.updated_at = utcnow()
        if requested == "active":
            row.next_run_at = next_occurrence(
                row.frequency,
                row.hour,
                row.minute,
                row.day_of_week,
                row.day_of_month,
                timezone_offset_minutes=row.timezone_offset_minutes or 0,
            )
        db.commit()
    return {"message": f"Schedule {requested}."}


@router.delete("/{schedule_id}")
def delete(schedule_id: int, user: dict = Depends(require_roles("owner", "admin"))):
    Session = get_session_factory()
    wid = user["workspace"]["id"]
    with Session() as db:
        row = db.scalar(
            select(AuditScheduleRecord).where(
                AuditScheduleRecord.id == schedule_id, AuditScheduleRecord.workspace_id == wid
            )
        )
        if not row:
            raise HTTPException(404, "Schedule not found.")
        db.delete(row)
        db.commit()
    return {"message": "Schedule deleted."}
