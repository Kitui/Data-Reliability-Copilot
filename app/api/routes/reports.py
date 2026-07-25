from __future__ import annotations
import csv, io, json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from sqlalchemy import select, func
from app.api.auth_dependencies import require_user
from app.db.models import (AuditRecord, DatasetRecord, IssueRecord, QualityRuleRecord, RuleExecutionRecord, DataContractRecord, ReportRecord, ReportScheduleRecord, AuditScheduleRecord, ScheduledAuditRunRecord, AlertRecord, ConnectorRecord, ActionPointRecord, UserRecord)
from app.db.session import get_session_factory
from app.versioning import lineage_audits

router=APIRouter(prefix="/reports",tags=["Reports"])

def now(): return datetime.now(timezone.utc)
def dt(v): return v.isoformat() if v else None

def _utc_naive(value):
    """Normalize SQLite/Python datetimes for safe comparisons.

    SQLite may return timezone-naive values even when the SQLAlchemy column is
    declared with ``timezone=True``. Overview aggregation compares persisted
    timestamps with a rolling UTC cutoff, so both sides must share the same
    representation.
    """
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value

def _scope(db,wid,date_from=None,date_to=None,dataset_id=None):
    q=select(AuditRecord).where(AuditRecord.workspace_id==wid)
    if date_from:q=q.where(AuditRecord.created_at>=date_from)
    if date_to:q=q.where(AuditRecord.created_at<=date_to)
    if dataset_id:
        d=db.scalar(select(DatasetRecord).where(DatasetRecord.id==dataset_id,DatasetRecord.workspace_id==wid))
        if not d:return [],None
        q=q.where(AuditRecord.dataset_name==d.name)
        return list(db.scalars(q.order_by(AuditRecord.created_at)).all()),d
    return list(db.scalars(q.order_by(AuditRecord.created_at)).all()),None

def _charts(db,wid,audits):
    audit_ids=[a.audit_id for a in audits]
    issues=list(db.scalars(select(IssueRecord).where(IssueRecord.audit_id.in_(audit_ids))).all()) if audit_ids else []
    execs=list(db.scalars(select(RuleExecutionRecord).where(RuleExecutionRecord.audit_id.in_(audit_ids))).all()) if audit_ids else []
    days={}
    for a in audits:
        key=a.created_at.strftime("%b %d")
        days.setdefault(key,[]).append(a.score)
    reliability=[{"label":k,"score":round(sum(v)/len(v),1)} for k,v in days.items()]
    sev=[{"label":s.title(),"count":sum(i.severity==s and i.status not in ('resolved','accepted') for i in issues)} for s in ('critical','high','medium','low')]
    categories={}
    columns={}
    for i in issues:
        categories[i.category]=categories.get(i.category,0)+1
        try:
            a=next((x for x in audits if x.audit_id==i.audit_id),None)
            payload=json.loads(a.payload_json) if a else {}
            match=next((x for x in payload.get('issues',[]) if x.get('issue_id')==i.issue_id),{})
            for c in match.get('columns',[]) or []:columns[c]=columns.get(c,0)+1
        except Exception:pass
    rule_by_day={}
    for e in execs:
        key=e.executed_at.strftime("%b %d") if e.executed_at else "Unknown"
        rec=rule_by_day.setdefault(key,[0,0]);rec[1]+=1;rec[0]+=e.outcome=='passed'
    pass_rate=[{"label":k,"rate":round(v[0]*100/v[1],1) if v[1] else 0} for k,v in rule_by_day.items()]
    latest={}
    for a in audits:latest[a.dataset_name]=a
    rankings=sorted([{"dataset":k,"score":v.score} for k,v in latest.items()],key=lambda x:x['score'],reverse=True)
    remediation=[]
    for a in audits:
        try:
            p=json.loads(a.payload_json)
            before=p.get('remediation',{}).get('before_score')
            if before is not None:remediation.append({"dataset":a.dataset_name,"before":before,"after":a.score})
        except Exception:pass
    return {"reliability":reliability,"severity":sev,"categories":[{"label":k.title(),"count":v} for k,v in sorted(categories.items(),key=lambda x:x[1],reverse=True)],
            "rule_pass_rate":pass_rate,"dataset_ranking":rankings[:10],"affected_columns":[{"column":k,"count":v} for k,v in sorted(columns.items(),key=lambda x:x[1],reverse=True)[:10]],
            "remediation_impact":remediation[:10],"score_issue_scatter":[{"dataset":a.dataset_name,"score":a.score,"issues":a.issue_count} for a in latest.values()]}

def _dashboard(db,wid,audits):
    ids=[a.audit_id for a in audits]
    issue_count=db.scalar(select(func.count()).select_from(IssueRecord).where(IssueRecord.audit_id.in_(ids),IssueRecord.status.not_in(['resolved','accepted']))) if ids else 0
    failed_rules=db.scalar(select(func.count()).select_from(RuleExecutionRecord).where(RuleExecutionRecord.audit_id.in_(ids),RuleExecutionRecord.outcome=='failed')) if ids else 0
    datasets=len({a.dataset_name for a in audits})
    latest={}
    for a in audits:latest[a.dataset_name]=a
    score=round(sum(a.score for a in latest.values())/len(latest),1) if latest else None
    contracts=db.scalar(select(func.count()).select_from(DataContractRecord).where(DataContractRecord.workspace_id==wid,DataContractRecord.validation_status=='failed')) or 0
    return {"score":score,"datasets":datasets,"active_issues":issue_count or 0,"failed_rules":failed_rules or 0,"contract_violations":contracts,"drift_events":sum(1 for a in audits if a.issue_count>0)//2}



def _safe_payload(audit):
    try:
        return json.loads(audit.payload_json or "{}")
    except Exception:
        return {}

def _issue_columns(audits, issues):
    audit_map={a.audit_id:_safe_payload(a) for a in audits}
    values={}
    for issue in issues:
        match=next((x for x in audit_map.get(issue.audit_id,{}).get("issues",[]) if x.get("issue_id")==issue.issue_id),{})
        for column in match.get("columns",[]) or []:
            values[column]=values.get(column,0)+1
    return values

@router.get("/overview")
def overview_command_centre(user:dict=Depends(require_user)):
    """Return the current operational posture plus clearly labelled history totals.

    Current metrics are derived from the newest audit for each dataset. Historical
    audit executions remain available in activity and all-time counters, but do
    not inflate active issues, failed rules, lifecycle totals, or version counts.
    """
    wid=user["workspace"]["id"];Session=get_session_factory();cutoff=_utc_naive(now()-timedelta(days=7))
    with Session() as db:
        audits=list(db.scalars(select(AuditRecord).where(AuditRecord.workspace_id==wid).order_by(AuditRecord.created_at.desc())).all())
        latest_by_dataset={}
        for audit in audits:
            latest_by_dataset.setdefault(audit.dataset_name,audit)
        latest=list(latest_by_dataset.values())
        latest_audit_ids=[a.audit_id for a in latest]

        datasets=list(db.scalars(select(DatasetRecord).where(DatasetRecord.workspace_id==wid).order_by(DatasetRecord.updated_at.desc())).all())
        current_issues=list(db.scalars(select(IssueRecord).where(IssueRecord.audit_id.in_(latest_audit_ids))).all()) if latest_audit_ids else []
        resolved_statuses={"resolved","fixed","accepted","dismissed","closed"}
        active_issues=[i for i in current_issues if i.status not in resolved_statuses]
        executions=list(db.scalars(select(RuleExecutionRecord).where(RuleExecutionRecord.audit_id.in_(latest_audit_ids)).order_by(RuleExecutionRecord.executed_at.desc())).all()) if latest_audit_ids else []
        rules=list(db.scalars(select(QualityRuleRecord).where(QualityRuleRecord.workspace_id==wid)).all())
        contract_rows=list(db.scalars(select(DataContractRecord).where(DataContractRecord.workspace_id==wid).order_by(DataContractRecord.updated_at.desc(),DataContractRecord.version.desc())).all())
        latest_contracts={}
        for contract in contract_rows:
            latest_contracts.setdefault(contract.contract_key,contract)
        contracts=list(latest_contracts.values())
        alerts=list(db.scalars(select(AlertRecord).where(AlertRecord.workspace_id==wid).order_by(AlertRecord.detected_at.desc())).all())
        schedules=list(db.scalars(select(AuditScheduleRecord).where(AuditScheduleRecord.workspace_id==wid).order_by(AuditScheduleRecord.next_run_at)).all())
        runs=list(db.scalars(select(ScheduledAuditRunRecord).where(ScheduledAuditRunRecord.workspace_id==wid).order_by(ScheduledAuditRunRecord.started_at.desc())).all())
        connectors=list(db.scalars(select(ConnectorRecord).where(ConnectorRecord.workspace_id==wid)).all())
        action_points=list(db.scalars(select(ActionPointRecord).where(ActionPointRecord.workspace_id==wid)).all())
        reports=list(db.scalars(select(ReportRecord).where(ReportRecord.workspace_id==wid)).all())

        score=round(sum(a.score for a in latest)/len(latest)) if latest else None
        previous=[a for a in audits if _utc_naive(a.created_at)<cutoff]
        previous_latest={}
        for a in previous: previous_latest.setdefault(a.dataset_name,a)
        previous_score=round(sum(a.score for a in previous_latest.values())/len(previous_latest)) if previous_latest else None
        score_delta=(score-previous_score) if score is not None and previous_score is not None else None
        severity={name:sum(i.severity==name for i in active_issues) for name in ("critical","high","medium","low")}

        lifecycle_buckets={name:[] for name in ("new","in_progress","resolved","reopened")}
        for issue in current_issues:
            raw=(issue.status or "open").lower()
            if raw in {"new","open"}: bucket="new"
            elif raw=="in_progress": bucket="in_progress"
            elif raw=="reopened": bucket="reopened"
            elif raw in resolved_statuses: bucket="resolved"
            else: bucket="new"
            lifecycle_buckets[bucket].append(issue)
        lifecycle=[]
        for status,bucket_issues in lifecycle_buckets.items():
            lifecycle.append({"status":status,"count":len(bucket_issues),**{level:sum(i.severity==level for i in bucket_issues) for level in ("critical","high","medium","low")}})

        failed_executions=[e for e in executions if e.outcome=="failed"]
        failed_rules=len(failed_executions)
        execution_total=len(executions)
        violated_contracts=[]
        contract_violation_count=0
        for contract in contracts:
            if contract.validation_status in ("failed","violation") or contract.status=="violation":
                violated_contracts.append(contract)
                try: validation=json.loads(contract.validation_json or "{}")
                except (TypeError,json.JSONDecodeError): validation={}
                contract_violation_count+=int(validation.get("violation_count") or 0)

        active_drift_alerts=[a for a in alerts if a.alert_type=="schema_drift" and a.status not in ("resolved","dismissed")]
        drift_datasets={a.dataset_name for a in active_drift_alerts if a.dataset_name}
        open_actions=[a for a in action_points if a.status not in ("resolved","completed","closed")]
        overdue_actions=[a for a in open_actions if a.priority=="critical"]
        active_schedules=[s for s in schedules if s.status=="active"]
        next_schedule=active_schedules[0] if active_schedules else None
        completed_runs=[r for r in runs if r.status=="completed" and _utc_naive(r.started_at)>=cutoff]
        failed_runs=[r for r in runs if r.status=="failed" and _utc_naive(r.started_at)>=cutoff]
        avg_duration=round(sum((r.duration_ms or 0) for r in completed_runs)/len(completed_runs)/1000,1) if completed_runs else 0
        scheduled_success_rate=round(len(completed_runs)*100/max(len(completed_runs)+len(failed_runs),1)) if (completed_runs or failed_runs) else 0
        recent_audits=[a for a in audits if _utc_naive(a.created_at)>=cutoff]
        # An AuditRecord represents a successfully completed audit. Failed schedule
        # attempts without an audit record are included in the denominator.
        audit_success_rate=round(len(recent_audits)*100/max(len(recent_audits)+len(failed_runs),1)) if (recent_audits or failed_runs) else 0

        recent_alerts=[a for a in alerts if a.status not in ("resolved","dismissed")][:5]
        activity=[]
        for a in audits[:5]: activity.append({"kind":"audit","title":f"Audit completed: {a.dataset_name}","time":dt(a.created_at),"status":"success","reference":a.audit_id})
        for r in executions[:4]: activity.append({"kind":"rule","title":f"Rule evaluation {r.outcome}: {r.message[:70]}","time":dt(r.executed_at),"status":"success" if r.outcome=="passed" else "warning","reference":r.audit_id})
        for c in contracts[:3]: activity.append({"kind":"contract","title":f"Contract {c.validation_status}: {c.name}","time":dt(c.updated_at),"status":"success" if c.validation_status=="passed" else "warning","reference":c.source_audit_id})
        for d in datasets[:3]: activity.append({"kind":"dataset","title":f"Dataset updated: {d.name}","time":dt(d.updated_at),"status":"info","dataset_id":d.id})
        activity=sorted(activity,key=lambda x:x.get("time") or "",reverse=True)[:7]
        domains=len({d.domain for d in datasets if d.domain})
        columns=_issue_columns(latest,active_issues)

        audits_by_dataset={}
        for audit in audits: audits_by_dataset.setdefault(audit.dataset_name,[]).append(audit)
        version_count=sum(len(lineage_audits(rows)) for rows in audits_by_dataset.values())

        return {
            "metrics":{"score":score,"score_delta":score_delta,"datasets":len(datasets),"domains":domains,"active_issues":len(active_issues),"severity":severity,"failed_rules":failed_rules,"rule_failure_rate":round(failed_rules*100/max(execution_total,1)),"contract_violations":contract_violation_count,"contracts_impacted":len(violated_contracts),"drift_events":len(drift_datasets),"drift_datasets":len(drift_datasets),"open_remediations":len(open_actions),"overdue_remediations":len(overdue_actions)},
            "ribbon":{"next_run_at":dt(next_schedule.next_run_at) if next_schedule else None,"next_schedule_name":next_schedule.name if next_schedule else None},
            "lifecycle":lifecycle,"severity":severity,"activity":activity,
            "alerts":[{"id":a.id,"title":a.title,"severity":a.severity,"detected_at":dt(a.detected_at),"alert_type":a.alert_type,"audit_id":a.audit_id} for a in recent_alerts],
            "upcoming":[{"id":s.id,"name":s.name,"frequency":s.frequency,"next_run_at":dt(s.next_run_at),"dataset_id":s.dataset_id} for s in active_schedules[:4]],
            "health":{"scheduled_runs":len(completed_runs),"audit_success_rate":scheduled_success_rate,"avg_audit_duration_seconds":avg_duration,"active_alerts":len(recent_alerts),"connector_status":"healthy" if connectors and all(c.status=="active" for c in connectors) else ("not_configured" if not connectors else "attention")},
            "platform":{"datasets":len(datasets),"versions":version_count,"audits_this_week":len(recent_audits),"success_rate":audit_success_rate,"active_users":1,"rules":len(rules),"contracts":len(contracts),"connectors":len(connectors),"reports":len(reports),"action_points":len(action_points)},
            "top_columns":[{"name":k,"count":v} for k,v in sorted(columns.items(),key=lambda x:x[1],reverse=True)[:5]]
        }

@router.get("")
def dashboard(date_from:datetime|None=None,date_to:datetime|None=None,dataset_id:int|None=None,report_type:str="executive",user:dict=Depends(require_user)):
    wid=user['workspace']['id'];Session=get_session_factory()
    with Session() as db:
        audits,_=_scope(db,wid,date_from,date_to,dataset_id)
        datasets=list(db.scalars(select(DatasetRecord).where(DatasetRecord.workspace_id==wid).order_by(DatasetRecord.name)).all())
        reports=list(db.scalars(select(ReportRecord).where(ReportRecord.workspace_id==wid).order_by(ReportRecord.generated_at.desc()).limit(20)).all())
        schedules=list(db.scalars(select(ReportScheduleRecord).where(ReportScheduleRecord.workspace_id==wid).order_by(ReportScheduleRecord.created_at.desc()).limit(10)).all())
        return {"metrics":_dashboard(db,wid,audits),"charts":_charts(db,wid,audits),"datasets":[{"id":d.id,"name":d.name} for d in datasets],
                "reports":[{"id":r.id,"name":r.name,"report_type":r.report_type,"format":r.format,"status":r.status,"generated_at":dt(r.generated_at)} for r in reports],
                "schedules":[{"id":s.id,"name":s.name,"report_type":s.report_type,"frequency":s.frequency,"format":s.format,"is_active":bool(s.is_active),"next_run_at":dt(s.next_run_at)} for s in schedules]}

class ReportCreate(BaseModel):
    name:str;report_type:str="executive";format:str="pdf";filters:dict={}
class ScheduleCreate(BaseModel):
    name:str;report_type:str="executive";frequency:str="weekly";format:str="pdf";filters:dict={}

@router.post("")
def create_report(body:ReportCreate,user:dict=Depends(require_user)):
    if body.format not in ('pdf','csv'):raise HTTPException(422,'Format must be PDF or CSV.')
    Session=get_session_factory();t=now()
    with Session() as db:
        r=ReportRecord(workspace_id=user['workspace']['id'],user_id=user['id'],name=body.name,report_type=body.report_type,format=body.format,filters_json=json.dumps(body.filters),status='completed',generated_at=t)
        db.add(r);db.commit();db.refresh(r);return {"id":r.id,"name":r.name,"format":r.format,"generated_at":r.generated_at}

@router.post("/schedules")
def create_schedule(body:ScheduleCreate,user:dict=Depends(require_user)):
    delta={'daily':timedelta(days=1),'weekly':timedelta(days=7),'monthly':timedelta(days=30)}.get(body.frequency,timedelta(days=7))
    Session=get_session_factory();t=now()
    with Session() as db:
        s=ReportScheduleRecord(workspace_id=user['workspace']['id'],user_id=user['id'],name=body.name,report_type=body.report_type,frequency=body.frequency,format=body.format,filters_json=json.dumps(body.filters),is_active=1,next_run_at=t+delta,created_at=t)
        db.add(s);db.commit();db.refresh(s);return {"id":s.id,"next_run_at":s.next_run_at}

@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id:int,user:dict=Depends(require_user)):
    Session=get_session_factory()
    with Session() as db:
        s=db.scalar(select(ReportScheduleRecord).where(ReportScheduleRecord.id==schedule_id,ReportScheduleRecord.workspace_id==user['workspace']['id']))
        if not s:raise HTTPException(404,'Report schedule not found.')
        db.delete(s);db.commit();return {"deleted":True}

def _csv_bytes(db,wid):
    audits=list(db.scalars(select(AuditRecord).where(AuditRecord.workspace_id==wid).order_by(AuditRecord.created_at.desc())).all())
    out=io.StringIO();w=csv.writer(out);w.writerow(['Dataset','Audit ID','Score','Issues','Risk','Generated At'])
    for a in audits:w.writerow([a.dataset_name,a.audit_id,a.score,a.issue_count,a.risk_level,a.created_at.isoformat()])
    return out.getvalue().encode()

def _pdf_bytes(title,metrics):
    lines=[title,'Data Reliability Copilot',f"Generated: {now().strftime('%Y-%m-%d %H:%M UTC')}",'',f"Overall reliability score: {metrics.get('score','—')}",f"Datasets monitored: {metrics.get('datasets',0)}",f"Active issues: {metrics.get('active_issues',0)}",f"Failed rules: {metrics.get('failed_rules',0)}"]
    text='\\n'.join(lines).replace('(','[').replace(')',']')
    stream=f"BT /F1 12 Tf 50 760 Td ({text}) Tj ET".encode()
    parts=[b'%PDF-1.4\n',b'1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n',b'2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n',b'3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >> endobj\n',f'4 0 obj << /Length {len(stream)} >> stream\n'.encode()+stream+b'\nendstream endobj\n',b'5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n']
    body=b''.join(parts);return body+b'trailer << /Root 1 0 R >>\n%%EOF'

@router.get("/export/{format}")
def export(format:str,user:dict=Depends(require_user)):
    Session=get_session_factory();wid=user['workspace']['id']
    with Session() as db:
        if format=='csv':return StreamingResponse(iter([_csv_bytes(db,wid)]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=reliability_report.csv'})
        audits,_=_scope(db,wid);metrics=_dashboard(db,wid,audits)
        return Response(_pdf_bytes('Executive Reliability Report',metrics),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename=reliability_report.pdf'})
