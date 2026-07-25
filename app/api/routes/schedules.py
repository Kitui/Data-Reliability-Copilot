from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.auth_dependencies import require_roles, require_user
from app.api.dependencies import get_audit_store
from app.api.routes.datasets import register_audit_dataset
from app.api.routes.quality_rules import assigned_rules_for_dataset, persist_rule_executions
from app.auditor import audit_dataframe
from app.core.config import get_settings
from app.db.models import AuditRecord, AuditScheduleRecord, DatasetRecord, ScheduledAuditRunRecord, UploadRecord
from app.db.session import get_session_factory
from app.ingestion import read_csv_path
from app.api.routes.audits import save_upload

router = APIRouter(prefix="/schedules", tags=["Scheduled Audits"])

_execution_lock = Lock()
_running_schedule_ids: set[int] = set()

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
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


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
    return candidate.astimezone(timezone.utc)


def serialize_schedule(row: AuditScheduleRecord, dataset: DatasetRecord | None, audit: AuditRecord | None) -> dict:
    return {
        "id": row.id, "dataset_id": row.dataset_id, "dataset_name": dataset.name if dataset else "Unavailable dataset",
        "source_type": dataset.source_type if dataset else "Unknown", "name": row.name, "frequency": row.frequency,
        "hour": row.hour, "minute": row.minute, "timezone_offset_minutes": row.timezone_offset_minutes or 0, "day_of_week": row.day_of_week, "day_of_month": row.day_of_month,
        "status": row.status, "next_run_at": ensure_utc(row.next_run_at), "last_run_at": ensure_utc(row.last_run_at),
        "last_status": row.last_status, "last_audit_id": row.last_audit_id, "last_error": row.last_error,
        "score": audit.score if audit else None, "issue_count": audit.issue_count if audit else None,
        "risk_level": audit.risk_level if audit else None,
    }


def execute_schedule(schedule_id: int, workspace_id: int, actor_name: str, triggered_by: str = "manual") -> dict:
    Session = get_session_factory(); started = utcnow(); timer = perf_counter()
    with Session() as db:
        schedule = db.scalar(select(AuditScheduleRecord).where(AuditScheduleRecord.id == schedule_id, AuditScheduleRecord.workspace_id == workspace_id))
        if not schedule: raise HTTPException(404, "Schedule not found.")
        dataset = db.scalar(select(DatasetRecord).where(DatasetRecord.id == schedule.dataset_id, DatasetRecord.workspace_id == workspace_id))
        run = ScheduledAuditRunRecord(schedule_id=schedule.id, workspace_id=workspace_id, dataset_id=schedule.dataset_id, status="in_progress", triggered_by=triggered_by, started_at=started)
        db.add(run); db.commit(); db.refresh(run); run_id = run.id
        latest_audit_id = dataset.latest_audit_id if dataset else None
        upload = db.scalar(select(UploadRecord).where(UploadRecord.audit_id == latest_audit_id)) if latest_audit_id else None
    try:
        if not dataset or not latest_audit_id: raise RuntimeError("The scheduled dataset has no completed source audit.")
        if upload:
            source_path = get_settings().root_dir / upload.relative_path
            if not source_path.exists(): raise RuntimeError("The source file is no longer available.")
            content = source_path.read_bytes()
            upload_info = save_upload(content, upload.original_filename, upload.content_type)
            frame = read_csv_path(source_path)
        else:
            source_path = get_settings().sample_dataset
            if dataset.name != source_path.name: raise RuntimeError("The scheduled dataset has no persisted source file.")
            content = source_path.read_bytes(); upload_info = save_upload(content, source_path.name, "text/csv"); frame = read_csv_path(source_path)
        rules = assigned_rules_for_dataset(workspace_id, dataset.name)
        result = audit_dataframe(frame, dataset.name, upload=upload_info, quality_rules=rules)
        result.audit_kind = "scheduled"
        try:
            source_payload = get_audit_store().get(latest_audit_id, workspace_id)
            result.dataset_version = source_payload.dataset_version if source_payload else None
        except Exception:
            result.dataset_version = None
        get_audit_store().save(result, workspace_id); persist_rule_executions(result.audit_id, result.rule_executions)
        register_audit_dataset(result, workspace_id, actor_name)
        completed = utcnow(); duration = int((perf_counter()-timer)*1000)
        with Session() as db:
            schedule = db.get(AuditScheduleRecord, schedule_id); run = db.get(ScheduledAuditRunRecord, run_id)
            run.audit_id=result.audit_id; run.status="completed"; run.completed_at=completed; run.duration_ms=duration; run.score=result.score.overall; run.issue_count=len(result.issues)
            schedule.last_run_at=completed; schedule.last_status="completed"; schedule.last_audit_id=result.audit_id; schedule.last_error=None
            schedule.next_run_at=next_occurrence(schedule.frequency,schedule.hour,schedule.minute,schedule.day_of_week,schedule.day_of_month,completed,schedule.timezone_offset_minutes or 0); schedule.updated_at=completed
            db.commit()
        return {"status":"completed","audit_id":result.audit_id,"score":result.score.overall,"issue_count":len(result.issues),"duration_ms":duration}
    except Exception as exc:
        completed=utcnow(); duration=int((perf_counter()-timer)*1000)
        with Session() as db:
            schedule=db.get(AuditScheduleRecord,schedule_id); run=db.get(ScheduledAuditRunRecord,run_id)
            run.status="failed"; run.completed_at=completed; run.duration_ms=duration; run.error_message=str(exc)
            schedule.last_run_at=completed; schedule.last_status="failed"; schedule.last_error=str(exc); schedule.next_run_at=next_occurrence(schedule.frequency,schedule.hour,schedule.minute,schedule.day_of_week,schedule.day_of_month,completed,schedule.timezone_offset_minutes or 0); schedule.updated_at=completed
            db.commit()
        raise HTTPException(409, str(exc))


def _claim_schedule(schedule_id: int) -> bool:
    with _execution_lock:
        if schedule_id in _running_schedule_ids:
            return False
        _running_schedule_ids.add(schedule_id)
        return True


def _release_schedule(schedule_id: int) -> None:
    with _execution_lock:
        _running_schedule_ids.discard(schedule_id)


def process_due(workspace_id: int, actor_name: str) -> None:
    Session=get_session_factory(); now=utcnow()
    with Session() as db:
        ids=list(db.scalars(select(AuditScheduleRecord.id).where(AuditScheduleRecord.workspace_id==workspace_id, AuditScheduleRecord.status=="active", AuditScheduleRecord.next_run_at<=now).order_by(AuditScheduleRecord.next_run_at)).all())
    for schedule_id in ids[:5]:
        if not _claim_schedule(schedule_id):
            continue
        try:
            execute_schedule(schedule_id, workspace_id, actor_name, "schedule")
        except HTTPException:
            pass
        finally:
            _release_schedule(schedule_id)


def process_all_due(actor_name: str = "Scheduled automation") -> int:
    """Execute due schedules across every workspace. Safe for the background poller."""
    Session=get_session_factory(); now=utcnow()
    with Session() as db:
        due=list(db.execute(select(AuditScheduleRecord.id, AuditScheduleRecord.workspace_id).where(AuditScheduleRecord.status=="active", AuditScheduleRecord.next_run_at<=now).order_by(AuditScheduleRecord.next_run_at).limit(25)).all())
    completed=0
    for schedule_id, workspace_id in due:
        if not _claim_schedule(schedule_id):
            continue
        try:
            execute_schedule(schedule_id, workspace_id, actor_name, "schedule")
            completed += 1
        except HTTPException:
            pass
        finally:
            _release_schedule(schedule_id)
    return completed


@router.get("")
def dashboard(timezone_offset_minutes: int | None = Query(default=None, ge=-840, le=840), user: dict = Depends(require_user)):
    wid=user["workspace"]["id"]; Session=get_session_factory()
    with Session() as db:
        schedules=list(db.scalars(select(AuditScheduleRecord).where(AuditScheduleRecord.workspace_id==wid).order_by(AuditScheduleRecord.next_run_at)).all())
        # Upgrade legacy schedules on first load using the browser's actual local
        # timezone. This repairs schedules created before timezone support.
        if timezone_offset_minutes is not None:
            changed=False
            for schedule in schedules:
                if schedule.timezone_offset_minutes is None:
                    schedule.timezone_offset_minutes=timezone_offset_minutes
                    schedule.next_run_at=next_occurrence(schedule.frequency,schedule.hour,schedule.minute,schedule.day_of_week,schedule.day_of_month,timezone_offset_minutes=timezone_offset_minutes)
                    changed=True
            if changed:
                db.commit()
                schedules=list(db.scalars(select(AuditScheduleRecord).where(AuditScheduleRecord.workspace_id==wid).order_by(AuditScheduleRecord.next_run_at)).all())
        datasets={x.id:x for x in db.scalars(select(DatasetRecord).where(DatasetRecord.workspace_id==wid)).all()}
        audit_ids=[x.last_audit_id for x in schedules if x.last_audit_id]
        audits={x.audit_id:x for x in db.scalars(select(AuditRecord).where(AuditRecord.audit_id.in_(audit_ids))).all()} if audit_ids else {}
        runs=list(db.scalars(select(ScheduledAuditRunRecord).where(ScheduledAuditRunRecord.workspace_id==wid).order_by(ScheduledAuditRunRecord.started_at.desc()).limit(50)).all())
    seven=utcnow()-timedelta(days=7); recent=[r for r in runs if (r.started_at.replace(tzinfo=timezone.utc) if r.started_at.tzinfo is None else r.started_at)>=seven]
    rows=[serialize_schedule(s,datasets.get(s.dataset_id),audits.get(s.last_audit_id)) for s in schedules]
    upcoming=sorted([r for r in rows if r["status"]=="active"],key=lambda x:x["next_run_at"])[:6]
    run_rows=[]
    for r in runs[:12]:
        d=datasets.get(r.dataset_id); run_rows.append({"id":r.id,"dataset_name":d.name if d else "Unavailable dataset","started_at":ensure_utc(r.started_at),"completed_at":ensure_utc(r.completed_at),"duration_ms":r.duration_ms,"status":r.status,"score":r.score,"issue_count":r.issue_count,"triggered_by":r.triggered_by,"audit_id":r.audit_id,"error_message":r.error_message})
    return {"schedules":rows,"upcoming":upcoming,"runs":run_rows,"metrics":{"total":len(rows),"active":sum(x["status"]=="active" for x in rows),"completed_7d":sum(x.status=="completed" for x in recent),"failed_7d":sum(x.status=="failed" for x in recent),"next_run_at":upcoming[0]["next_run_at"] if upcoming else None}}

@router.post("")
def create(payload: ScheduleCreate, user: dict = Depends(require_roles("owner","admin"))):
    wid=user["workspace"]["id"]; Session=get_session_factory(); now=utcnow()
    with Session() as db:
        dataset=db.scalar(select(DatasetRecord).where(DatasetRecord.id==payload.dataset_id,DatasetRecord.workspace_id==wid))
        if not dataset: raise HTTPException(404,"Dataset not found.")
        row=AuditScheduleRecord(workspace_id=wid,dataset_id=dataset.id,name=payload.name or f"{dataset.name} audit",frequency=payload.frequency,hour=payload.hour,minute=payload.minute,timezone_offset_minutes=payload.timezone_offset_minutes,day_of_week=payload.day_of_week,day_of_month=payload.day_of_month,status="active",next_run_at=next_occurrence(payload.frequency,payload.hour,payload.minute,payload.day_of_week,payload.day_of_month,timezone_offset_minutes=payload.timezone_offset_minutes),created_by_user_id=user["id"],created_at=now,updated_at=now)
        db.add(row);db.commit();db.refresh(row)
        return {"id":row.id,"message":"Schedule created."}

@router.post("/{schedule_id}/run")
def run_now(schedule_id:int,user:dict=Depends(require_roles("owner","admin"))):
    return execute_schedule(schedule_id,user["workspace"]["id"],str(user.get("full_name") or "Workspace team"),"manual")

@router.patch("/{schedule_id}/status")
def status(schedule_id:int,payload:dict,user:dict=Depends(require_roles("owner","admin"))):
    requested=payload.get("status");
    if requested not in {"active","paused"}: raise HTTPException(400,"Status must be active or paused.")
    Session=get_session_factory();wid=user["workspace"]["id"]
    with Session() as db:
        row=db.scalar(select(AuditScheduleRecord).where(AuditScheduleRecord.id==schedule_id,AuditScheduleRecord.workspace_id==wid))
        if not row: raise HTTPException(404,"Schedule not found.")
        row.status=requested;row.updated_at=utcnow()
        if requested=="active": row.next_run_at=next_occurrence(row.frequency,row.hour,row.minute,row.day_of_week,row.day_of_month,timezone_offset_minutes=row.timezone_offset_minutes or 0)
        db.commit()
    return {"message":f"Schedule {requested}."}

@router.delete("/{schedule_id}")
def delete(schedule_id:int,user:dict=Depends(require_roles("owner","admin"))):
    Session=get_session_factory();wid=user["workspace"]["id"]
    with Session() as db:
        row=db.scalar(select(AuditScheduleRecord).where(AuditScheduleRecord.id==schedule_id,AuditScheduleRecord.workspace_id==wid))
        if not row: raise HTTPException(404,"Schedule not found.")
        db.delete(row);db.commit()
    return {"message":"Schedule deleted."}
