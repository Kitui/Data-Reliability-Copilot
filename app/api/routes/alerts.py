from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.auth_dependencies import require_user
from app.db.models import (
    AlertRecord, AuditRecord, DataContractRecord, DatasetRecord, IssueRecord,
    NotificationPreferenceRecord, QualityRuleRecord, RuleExecutionRecord,
    ScheduledAuditRunRecord,
)
from app.db.session import get_session_factory
from app.api.routes.schema_drift import _all_events

router = APIRouter(prefix="/alerts", tags=["Alerts & Notifications"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _upsert(db, workspace_id: int, *, fingerprint: str, alert_type: str, severity: str,
            title: str, description: str, potential_impact: str | None = None,
            dataset_id: int | None = None, dataset_name: str | None = None,
            audit_id: str | None = None, rule_id: int | None = None,
            contract_id: int | None = None, reference: dict | None = None,
            detected_at: datetime | None = None) -> AlertRecord:
    row = db.scalar(select(AlertRecord).where(
        AlertRecord.workspace_id == workspace_id,
        AlertRecord.fingerprint == fingerprint,
    ))
    now = utcnow()
    if row is None:
        row = AlertRecord(
            workspace_id=workspace_id, fingerprint=fingerprint, alert_type=alert_type,
            severity=severity, status="new", title=title, description=description,
            potential_impact=potential_impact, dataset_id=dataset_id,
            dataset_name=dataset_name, audit_id=audit_id, rule_id=rule_id,
            contract_id=contract_id, reference_json=json.dumps(reference or {}),
            detected_at=detected_at or now, updated_at=now,
        )
        db.add(row)
    else:
        row.severity = severity
        row.title = title
        row.description = description
        row.potential_impact = potential_impact
        row.reference_json = json.dumps(reference or {})
        row.updated_at = now
    return row


def sync_alerts(workspace_id: int, user_id: int) -> None:
    Session = get_session_factory()
    with Session() as db:
        pref = db.scalar(select(NotificationPreferenceRecord).where(
            NotificationPreferenceRecord.workspace_id == workspace_id,
            NotificationPreferenceRecord.user_id == user_id,
        ))
        threshold = pref.score_threshold if pref else 80
        datasets = {d.id: d for d in db.scalars(select(DatasetRecord).where(DatasetRecord.workspace_id == workspace_id)).all()}
        audits = list(db.scalars(select(AuditRecord).where(AuditRecord.workspace_id == workspace_id).order_by(AuditRecord.created_at.desc()).limit(80)).all())
        latest_by_dataset: dict[str, AuditRecord] = {}
        for audit in audits:
            latest_by_dataset.setdefault(audit.dataset_name, audit)
        for audit in latest_by_dataset.values():
            dataset = next((d for d in datasets.values() if d.name == audit.dataset_name), None)
            if audit.score < threshold:
                severity = "critical" if audit.score < max(60, threshold - 15) else "high"
                _upsert(db, workspace_id,
                    fingerprint=f"score:{audit.audit_id}:{threshold}", alert_type="score_threshold",
                    severity=severity, title=f"Reliability score below threshold ({threshold}%)",
                    description=f"The latest audit score is {audit.score}, below the configured threshold of {threshold}.",
                    potential_impact="Data quality may be insufficient for trusted analysis and reporting.",
                    dataset_id=dataset.id if dataset else None, dataset_name=audit.dataset_name,
                    audit_id=audit.audit_id, reference={"score": audit.score, "threshold": threshold},
                    detected_at=audit.created_at)
            high_issues = list(db.scalars(select(IssueRecord).where(
                IssueRecord.audit_id == audit.audit_id,
                IssueRecord.severity.in_(["critical", "high"]),
                IssueRecord.status != "resolved",
            )).all())
            if high_issues:
                severity = "critical" if any(x.severity == "critical" for x in high_issues) else "high"
                _upsert(db, workspace_id,
                    fingerprint=f"issues:{audit.audit_id}", alert_type="high_severity_issue",
                    severity=severity, title="High severity issues detected",
                    description=f"{len(high_issues)} critical or high-severity issues require review.",
                    potential_impact="Unresolved issues may affect downstream decisions, compliance, or operational reliability.",
                    dataset_id=dataset.id if dataset else None, dataset_name=audit.dataset_name,
                    audit_id=audit.audit_id, reference={"issue_count": len(high_issues)},
                    detected_at=audit.created_at)
        failed_execs = list(db.scalars(select(RuleExecutionRecord).join(
            AuditRecord, AuditRecord.audit_id == RuleExecutionRecord.audit_id
        ).where(AuditRecord.workspace_id == workspace_id, RuleExecutionRecord.outcome == "failed").order_by(RuleExecutionRecord.executed_at.desc()).limit(50)).all())
        for execution in failed_execs:
            audit = db.get(AuditRecord, execution.audit_id)
            rule = db.get(QualityRuleRecord, execution.rule_id) if execution.rule_id else None
            dataset = next((d for d in datasets.values() if audit and d.name == audit.dataset_name), None)
            _upsert(db, workspace_id,
                fingerprint=f"rule:{execution.id}", alert_type="rule_failure",
                severity=(rule.severity if rule else "medium"), title="Quality rule failed",
                description=execution.message, potential_impact="Failed quality rules may invalidate expected business constraints.",
                dataset_id=dataset.id if dataset else None, dataset_name=audit.dataset_name if audit else None,
                audit_id=execution.audit_id, rule_id=execution.rule_id,
                reference={"rule_name": rule.name if rule else "Quality rule", "affected_rows": execution.affected_rows},
                detected_at=execution.executed_at)
        contracts = list(db.scalars(select(DataContractRecord).where(
            DataContractRecord.workspace_id == workspace_id,
            DataContractRecord.validation_status == "failed",
        ).order_by(DataContractRecord.updated_at.desc()).limit(40)).all())
        for contract in contracts:
            dataset = datasets.get(contract.dataset_id)
            _upsert(db, workspace_id,
                fingerprint=f"contract:{contract.id}:{contract.version}", alert_type="contract_violation",
                severity="high", title="Data contract violation",
                description=f"{contract.name} version {contract.version} failed validation.",
                potential_impact="Contract violations can break downstream interfaces and governed data expectations.",
                dataset_id=contract.dataset_id, dataset_name=dataset.name if dataset else None,
                audit_id=contract.source_audit_id, contract_id=contract.id,
                reference={"contract_name": contract.name, "version": contract.version},
                detected_at=contract.updated_at)
        for event in _all_events(workspace_id):
            if event.get("status") == "resolved":
                continue
            _upsert(db, workspace_id,
                fingerprint=f"drift:{event['id']}", alert_type="schema_drift",
                severity=event.get("severity", "medium"), title="Schema drift detected",
                description=event.get("description", "Dataset schema drift was detected."),
                potential_impact="Unexpected schema or profile changes may break data consumers and contract expectations.",
                dataset_id=event.get("dataset_id"), dataset_name=event.get("dataset_name"),
                audit_id=event.get("candidate_audit_id"),
                reference={"drift_type": event.get("drift_type"), "impact_score": event.get("impact_score"),
                           "baseline_version": event.get("baseline_version"), "candidate_version": event.get("candidate_version")},
                detected_at=event.get("detected_at"))
        failed_runs = list(db.scalars(select(ScheduledAuditRunRecord).where(
            ScheduledAuditRunRecord.workspace_id == workspace_id,
            ScheduledAuditRunRecord.status == "failed",
        ).order_by(ScheduledAuditRunRecord.started_at.desc()).limit(40)).all())
        for run in failed_runs:
            dataset = datasets.get(run.dataset_id)
            _upsert(db, workspace_id,
                fingerprint=f"schedule:{run.id}", alert_type="scheduled_audit_failure",
                severity="critical", title="Scheduled audit failed",
                description=run.error_message or "The scheduled audit did not complete successfully.",
                potential_impact="Monitoring coverage is interrupted until the schedule failure is resolved.",
                dataset_id=run.dataset_id, dataset_name=dataset.name if dataset else None,
                audit_id=run.audit_id, reference={"run_id": run.id, "schedule_id": run.schedule_id},
                detected_at=run.started_at)
        db.commit()


def serialize(row: AlertRecord) -> dict:
    return {
        "id": row.id, "alert_type": row.alert_type, "severity": row.severity,
        "status": row.status, "title": row.title, "description": row.description,
        "potential_impact": row.potential_impact, "dataset_id": row.dataset_id,
        "dataset_name": row.dataset_name, "audit_id": row.audit_id,
        "rule_id": row.rule_id, "contract_id": row.contract_id,
        "reference": json.loads(row.reference_json or "{}"),
        "detected_at": ensure_utc(row.detected_at), "read_at": ensure_utc(row.read_at),
        "acknowledged_at": ensure_utc(row.acknowledged_at),
        "resolved_at": ensure_utc(row.resolved_at), "dismissed_at": ensure_utc(row.dismissed_at),
    }


@router.get("")
def dashboard(
    search: str | None = None, severity: str | None = None, status: str | None = None,
    alert_type: str | None = None, dataset_id: int | None = None,
    date_from: datetime | None = None, date_to: datetime | None = None,
    page: int = Query(default=1, ge=1), page_size: int = Query(default=8, ge=1, le=50),
    user: dict = Depends(require_user),
):
    workspace_id = user["workspace"]["id"]
    sync_alerts(workspace_id, user["id"])
    Session = get_session_factory()
    with Session() as db:
        query = select(AlertRecord).where(AlertRecord.workspace_id == workspace_id)
        if search:
            term = f"%{search.strip()}%"
            query = query.where((AlertRecord.title.ilike(term)) | (AlertRecord.dataset_name.ilike(term)) | (AlertRecord.description.ilike(term)))
        if severity and severity != "all": query = query.where(AlertRecord.severity == severity)
        if status and status != "all": query = query.where(AlertRecord.status == status)
        if alert_type and alert_type != "all": query = query.where(AlertRecord.alert_type == alert_type)
        if dataset_id: query = query.where(AlertRecord.dataset_id == dataset_id)
        if date_from: query = query.where(AlertRecord.detected_at >= date_from)
        if date_to: query = query.where(AlertRecord.detected_at <= date_to)
        rows = list(db.scalars(query.order_by(AlertRecord.detected_at.desc())).all())
        all_rows = list(db.scalars(select(AlertRecord).where(AlertRecord.workspace_id == workspace_id)).all())
        datasets = list(db.scalars(select(DatasetRecord).where(DatasetRecord.workspace_id == workspace_id).order_by(DatasetRecord.name)).all())
        start = (page - 1) * page_size
        page_rows = rows[start:start + page_size]
        metrics = {
            "critical": sum(x.severity == "critical" and x.status not in ("resolved", "dismissed") for x in all_rows),
            "high": sum(x.severity == "high" and x.status not in ("resolved", "dismissed") for x in all_rows),
            "unread": sum(x.status == "new" for x in all_rows),
            "resolved": sum(x.status == "resolved" for x in all_rows),
            "total": len(all_rows),
            "acknowledged": sum(x.status == "acknowledged" for x in all_rows),
            "dismissed": sum(x.status == "dismissed" for x in all_rows),
        }
    return {"alerts": [serialize(x) for x in page_rows], "metrics": metrics,
            "datasets": [{"id": d.id, "name": d.name} for d in datasets],
            "pagination": {"page": page, "page_size": page_size, "total": len(rows), "pages": max(1, (len(rows)+page_size-1)//page_size)}}


class AlertAction(BaseModel):
    action: str = Field(pattern="^(read|unread|acknowledge|resolve|dismiss|reopen)$")


@router.patch("/{alert_id}")
def update_alert(alert_id: int, payload: AlertAction, user: dict = Depends(require_user)):
    wid = user["workspace"]["id"]; now = utcnow(); Session = get_session_factory()
    with Session() as db:
        row = db.scalar(select(AlertRecord).where(AlertRecord.id == alert_id, AlertRecord.workspace_id == wid))
        if not row: raise HTTPException(404, "Alert not found.")
        if payload.action == "read": row.read_at = now; row.status = "read" if row.status == "new" else row.status
        elif payload.action == "unread": row.read_at = None; row.status = "new"
        elif payload.action == "acknowledge": row.status = "acknowledged"; row.acknowledged_at = now; row.acknowledged_by_user_id = user["id"]
        elif payload.action == "resolve": row.status = "resolved"; row.resolved_at = now; row.resolved_by_user_id = user["id"]
        elif payload.action == "dismiss": row.status = "dismissed"; row.dismissed_at = now
        elif payload.action == "reopen": row.status = "new"; row.resolved_at = None; row.dismissed_at = None; row.acknowledged_at = None
        row.updated_at = now; db.commit(); db.refresh(row)
        return serialize(row)


class PreferencePayload(BaseModel):
    in_app_enabled: bool = True
    email_enabled: bool = False
    critical_enabled: bool = True
    high_enabled: bool = True
    medium_enabled: bool = True
    low_enabled: bool = False
    score_threshold: int = Field(default=80, ge=0, le=100)


@router.get("/preferences/me")
def get_preferences(user: dict = Depends(require_user)):
    wid=user["workspace"]["id"]; Session=get_session_factory()
    with Session() as db:
        row=db.scalar(select(NotificationPreferenceRecord).where(NotificationPreferenceRecord.workspace_id==wid,NotificationPreferenceRecord.user_id==user["id"]))
        if not row:
            return PreferencePayload().model_dump()
        return {k:bool(getattr(row,k)) for k in ["in_app_enabled","email_enabled","critical_enabled","high_enabled","medium_enabled","low_enabled"]} | {"score_threshold":row.score_threshold}


@router.put("/preferences/me")
def save_preferences(payload: PreferencePayload, user: dict = Depends(require_user)):
    wid=user["workspace"]["id"]; Session=get_session_factory(); now=utcnow()
    with Session() as db:
        row=db.scalar(select(NotificationPreferenceRecord).where(NotificationPreferenceRecord.workspace_id==wid,NotificationPreferenceRecord.user_id==user["id"]))
        if not row:
            row=NotificationPreferenceRecord(workspace_id=wid,user_id=user["id"],updated_at=now);db.add(row)
        for field,value in payload.model_dump().items(): setattr(row,field,int(value) if isinstance(value,bool) else value)
        row.updated_at=now;db.commit()
    return payload.model_dump()


@router.get("/export.csv")
def export_csv(user: dict = Depends(require_user)):
    wid=user["workspace"]["id"]; sync_alerts(wid,user["id"]); Session=get_session_factory()
    with Session() as db: rows=list(db.scalars(select(AlertRecord).where(AlertRecord.workspace_id==wid).order_by(AlertRecord.detected_at.desc())).all())
    output=io.StringIO(); writer=csv.writer(output); writer.writerow(["Alert","Type","Severity","Status","Dataset","Detected at","Audit ID","Description"])
    for row in rows: writer.writerow([row.title,row.alert_type,row.severity,row.status,row.dataset_name or "",ensure_utc(row.detected_at).isoformat(),row.audit_id or "",row.description])
    return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=alerts_report.csv"})
