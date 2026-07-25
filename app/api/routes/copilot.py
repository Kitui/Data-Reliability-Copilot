from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete, update, delete, update
from app.api.auth_dependencies import require_user
from app.db.models import (ActionPointRecord, AuditRecord, CopilotMessageRecord, CopilotSessionRecord,
    DataContractRecord, DatasetRecord, QualityRuleRecord, RuleExecutionRecord)
from app.db.session import get_session_factory

router=APIRouter(prefix="/copilot",tags=["Reliability Copilot"])

def now(): return datetime.now(timezone.utc)
def payload(a:AuditRecord|None)->dict[str,Any]:
    if not a:return {}
    try:return json.loads(a.payload_json)
    except:return {}
def audit_summary(a:AuditRecord|None)->dict[str,Any]|None:
    if not a:return None
    p=payload(a);issues=p.get("issues",[]);rules=p.get("rule_executions",[])
    sev={k:sum(1 for x in issues if x.get("severity")==k and x.get("status") not in ("resolved","accepted")) for k in ("critical","high","medium","low")}
    failed=[x for x in rules if x.get("outcome")=="failed"]
    columns=[]
    for x in issues:
        for c in x.get("columns",[]) or []:
            if c not in columns:columns.append(c)
    return {"audit_id":a.audit_id,"dataset_name":a.dataset_name,"created_at":a.created_at,"score":a.score,"risk_level":a.risk_level,
            "issue_count":a.issue_count,"severity":sev,"failed_rules":len(failed),"top_columns":columns[:8],"issues":issues,"rule_executions":rules}

def find_audit(db,wid,audit_id=None,dataset_id=None):
    if audit_id:return db.scalar(select(AuditRecord).where(AuditRecord.audit_id==audit_id,AuditRecord.workspace_id==wid))
    if dataset_id:
        d=db.scalar(select(DatasetRecord).where(DatasetRecord.id==dataset_id,DatasetRecord.workspace_id==wid))
        if d and d.latest_audit_id:return db.scalar(select(AuditRecord).where(AuditRecord.audit_id==d.latest_audit_id,AuditRecord.workspace_id==wid))
    return db.scalar(select(AuditRecord).where(AuditRecord.workspace_id==wid).order_by(AuditRecord.created_at.desc()))

def evidence(db,wid,audit,dataset_id=None,compare=None):
    current=audit_summary(audit);previous=audit_summary(compare)
    ds=None
    if dataset_id: ds=db.scalar(select(DatasetRecord).where(DatasetRecord.id==dataset_id,DatasetRecord.workspace_id==wid))
    elif audit: ds=db.scalar(select(DatasetRecord).where(DatasetRecord.workspace_id==wid,DatasetRecord.name==audit.dataset_name))
    did=ds.id if ds else None
    contracts=db.scalars(select(DataContractRecord).where(DataContractRecord.workspace_id==wid,DataContractRecord.dataset_id==did)).all() if did else []
    failed_contracts=sum(1 for x in contracts if x.validation_status not in ("passed","not_validated"))
    failed_rules=0
    if audit: failed_rules=db.scalar(select(func.count()).select_from(RuleExecutionRecord).where(RuleExecutionRecord.audit_id==audit.audit_id,RuleExecutionRecord.outcome=="failed")) or 0
    return {"dataset":({"id":ds.id,"name":ds.name,"record_count":ds.record_count,"column_count":ds.column_count} if ds else None),
            "current":current,"previous":previous,"contract_violations":failed_contracts,"failed_rules":failed_rules,"drift_events":max(0,(current or {}).get("severity",{}).get("medium",0)//2),
            "score_change":((current["score"]-previous["score"]) if current and previous else None)}

def formulate(question:str,ev:dict,mode:str):
    clean_question = " ".join(question.strip().split())
    normalized = re.sub(r"[^a-z0-9\s']", "", clean_question.lower()).strip()
    greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "how are you", "hello copilot", "hi copilot", "hey copilot"}
    if normalized in greetings:
        return {
            "response_type": "conversation",
            "answer": "Hello! I’m the Reliability Copilot. Select a dataset and audit when you want evidence-grounded analysis, or ask me about scores, issues, failed rules, schema drift, contracts, or remediation.",
            "summary": {}, "factors": [], "actions": [], "evidence": {},
        }

    c=ev.get("current") or {};p=ev.get("previous") or {};change=ev.get("score_change")
    if not c:
        return {
            "response_type": "empty_context",
            "answer": "I don’t have an audit selected yet. Choose a dataset and audit from Copilot Context, or run an audit first so I can ground the answer in platform evidence.",
            "summary": {}, "factors": [],
            "actions": ["Select a registered dataset.", "Choose a completed audit run or run a new audit."],
            "evidence": {},
        }

    sev=c.get("severity",{});issues=c.get("issues",[]);rules=c.get("rule_executions",[])
    failed=[r for r in rules if r.get("outcome")=="failed"]
    top=sorted(issues,key=lambda x:({"critical":4,"high":3,"medium":2,"low":1}.get(x.get("severity"),0),x.get("affected_rows",0)),reverse=True)[:4]
    q=clean_question.lower()
    if "score" in q or "drop" in q or mode=="score":
        direction="changed" if change is None else ("improved" if change>0 else "dropped" if change<0 else "remained stable")
        lead=f"The latest reliability score is {c.get('score','—')}/100"
        if change is not None:lead+=f" and {direction} by {abs(change)} points from {p.get('score','—')}/100."
        else:lead+="."
    elif "rule" in q or mode=="rules": lead=f"The latest audit contains {len(failed)} failed quality rules."
    elif "drift" in q or mode=="drift": lead=f"The current evidence indicates {ev.get('drift_events',0)} material schema or profile drift signals."
    elif "contract" in q or mode=="contracts": lead=f"There are {ev.get('contract_violations',0)} contract validation results requiring attention."
    elif "compare" in q or mode=="comparison": lead=f"The selected audits compare at {p.get('score','—')}/100 versus {c.get('score','—')}/100."
    else: lead=f"The latest audit for {c.get('dataset_name','the selected dataset')} scored {c.get('score','—')}/100 with {c.get('issue_count',0)} active issues."
    factors=[]
    for x in top:
        factors.append({"title":x.get("title") or x.get("message") or "Quality issue","severity":x.get("severity","medium"),"affected_rows":x.get("affected_rows",0),"columns":x.get("columns",[])})
    actions=[]
    for x in factors[:4]:
        cols=", ".join(x["columns"][:2]) if x["columns"] else "the affected fields"
        actions.append(f"Review {cols} and validate the upstream source or transformation responsible for {x['title'].lower()}.")
    if failed:actions.append("Review the highest-impact failed rules and create or strengthen a governed rule draft before the next audit.")
    if not actions:actions=["Continue monitoring the dataset and compare the next audit against this baseline."]
    return {"response_type":"analysis","answer":lead,"summary":{"critical":sev.get("critical",0),"high":sev.get("high",0),"passed_rules":sum(1 for r in rules if r.get("outcome")=="passed")},
            "factors":factors,"actions":actions[:5],"evidence":{"failed_rules":len(failed),"contract_violations":ev.get("contract_violations",0),"drift_events":ev.get("drift_events",0),"audit_id":c.get("audit_id"),"dataset":c.get("dataset_name"),"columns":c.get("top_columns",[])}}

class SessionCreate(BaseModel):
    dataset_id:int|None=None;audit_id:str|None=None;compare_audit_id:str|None=None;analysis_mode:str="general";title:str|None=None
class AskBody(BaseModel):
    question:str=Field(min_length=2,max_length=2000);dataset_id:int|None=None;audit_id:str|None=None;compare_audit_id:str|None=None;analysis_mode:str="general"
class ActionCreate(BaseModel):
    title:str;description:str;priority:str="medium";dataset_id:int|None=None;audit_id:str|None=None;session_id:int|None=None

@router.get("/context")
def context(dataset_id:str|None=None,audit_id:str|None=None,compare_audit_id:str|None=None,user:dict=Depends(require_user)):
    dataset_id = dataset_id.strip() if isinstance(dataset_id, str) else dataset_id
    if dataset_id == "": dataset_id = None
    if dataset_id is not None:
        try: dataset_id = int(dataset_id)
        except (TypeError, ValueError): raise HTTPException(422, "Dataset ID must be a valid integer.")
    audit_id = audit_id.strip() if isinstance(audit_id, str) else audit_id
    compare_audit_id = compare_audit_id.strip() if isinstance(compare_audit_id, str) else compare_audit_id
    audit_id = audit_id or None
    compare_audit_id = compare_audit_id or None
    wid=user["workspace"]["id"];Session=get_session_factory()
    with Session() as db:
        datasets=db.scalars(select(DatasetRecord).where(DatasetRecord.workspace_id==wid).order_by(DatasetRecord.name)).all()
        audits=db.scalars(select(AuditRecord).where(AuditRecord.workspace_id==wid).order_by(AuditRecord.created_at.desc())).all()
        current=find_audit(db,wid,audit_id,dataset_id);compare=find_audit(db,wid,compare_audit_id,None) if compare_audit_id else (next((a for a in audits if current and a.dataset_name==current.dataset_name and a.audit_id!=current.audit_id),None))
        ev=evidence(db,wid,current,dataset_id,compare)
        sessions=db.scalars(select(CopilotSessionRecord).where(CopilotSessionRecord.workspace_id==wid,CopilotSessionRecord.user_id==user["id"]).order_by(CopilotSessionRecord.updated_at.desc()).limit(10)).all()
        return {"datasets":[{"id":d.id,"name":d.name,"latest_audit_id":d.latest_audit_id} for d in datasets],"audits":[{"audit_id":a.audit_id,"dataset_name":a.dataset_name,"created_at":a.created_at,"score":a.score} for a in audits],"selected":ev,"sessions":[{"id":s.id,"title":s.title,"updated_at":s.updated_at,"dataset_id":s.dataset_id,"audit_id":s.audit_id,"compare_audit_id":s.compare_audit_id,"analysis_mode":s.analysis_mode} for s in sessions]}

@router.post("/sessions")
def create_session(body:SessionCreate,user:dict=Depends(require_user)):
    t=now();Session=get_session_factory()
    with Session() as db:
        s=CopilotSessionRecord(workspace_id=user["workspace"]["id"],user_id=user["id"],dataset_id=body.dataset_id,audit_id=body.audit_id,compare_audit_id=body.compare_audit_id,analysis_mode=body.analysis_mode,title=body.title or "New Copilot session",created_at=t,updated_at=t);db.add(s);db.commit();db.refresh(s);return {"id":s.id,"title":s.title}

@router.get("/sessions/{session_id}")
def get_session(session_id:int,user:dict=Depends(require_user)):
    wid=user["workspace"]["id"];Session=get_session_factory()
    with Session() as db:
        s=db.scalar(select(CopilotSessionRecord).where(CopilotSessionRecord.id==session_id,CopilotSessionRecord.workspace_id==wid,CopilotSessionRecord.user_id==user["id"]))
        if not s:raise HTTPException(404,"Copilot session not found.")
        msgs=db.scalars(select(CopilotMessageRecord).where(CopilotMessageRecord.session_id==s.id).order_by(CopilotMessageRecord.created_at)).all()
        return {"session":{"id":s.id,"title":s.title,"dataset_id":s.dataset_id,"audit_id":s.audit_id,"compare_audit_id":s.compare_audit_id,"analysis_mode":s.analysis_mode},"messages":[{"id":m.id,"role":m.role,"content":m.content,"evidence":json.loads(m.evidence_json or "{}"),"created_at":m.created_at} for m in msgs]}


@router.delete("/sessions/{session_id}")
def delete_session(session_id:int,user:dict=Depends(require_user)):
    wid=user["workspace"]["id"];Session=get_session_factory()
    with Session() as db:
        s=db.scalar(select(CopilotSessionRecord).where(CopilotSessionRecord.id==session_id,CopilotSessionRecord.workspace_id==wid,CopilotSessionRecord.user_id==user["id"]))
        if not s:raise HTTPException(404,"Copilot session not found.")
        db.execute(update(ActionPointRecord).where(ActionPointRecord.session_id==s.id,ActionPointRecord.workspace_id==wid).values(session_id=None))
        db.execute(delete(CopilotMessageRecord).where(CopilotMessageRecord.session_id==s.id,CopilotMessageRecord.workspace_id==wid))
        db.delete(s);db.commit()
        return {"deleted":True,"session_id":session_id}

@router.post("/sessions/{session_id}/ask")
def ask(session_id:int,body:AskBody,user:dict=Depends(require_user)):
    wid=user["workspace"]["id"];Session=get_session_factory();t=now()
    with Session() as db:
        s=db.scalar(select(CopilotSessionRecord).where(CopilotSessionRecord.id==session_id,CopilotSessionRecord.workspace_id==wid,CopilotSessionRecord.user_id==user["id"]))
        if not s:raise HTTPException(404,"Copilot session not found.")
        s.dataset_id=body.dataset_id or s.dataset_id;s.audit_id=body.audit_id or s.audit_id;s.compare_audit_id=body.compare_audit_id or s.compare_audit_id;s.analysis_mode=body.analysis_mode or s.analysis_mode
        current=find_audit(db,wid,s.audit_id,s.dataset_id);compare=find_audit(db,wid,s.compare_audit_id,None) if s.compare_audit_id else None
        ev=evidence(db,wid,current,s.dataset_id,compare);result=formulate(body.question,ev,s.analysis_mode)
        if s.title=="New Copilot session":s.title=body.question[:80]
        s.updated_at=t
        db.add(CopilotMessageRecord(session_id=s.id,workspace_id=wid,role="user",content=body.question,evidence_json="{}",created_at=t))
        db.add(CopilotMessageRecord(session_id=s.id,workspace_id=wid,role="assistant",content=result["answer"],evidence_json=json.dumps(result),created_at=t));db.commit()
        return {"session_id":s.id,"title":s.title,"response":result,"context":ev}

@router.post("/action-points")
def action_point(body:ActionCreate,user:dict=Depends(require_user)):
    Session=get_session_factory()
    with Session() as db:
        x=ActionPointRecord(workspace_id=user["workspace"]["id"],dataset_id=body.dataset_id,audit_id=body.audit_id,session_id=body.session_id,title=body.title,description=body.description,priority=body.priority,status="open",created_by_user_id=user["id"],created_at=now());db.add(x);db.commit();db.refresh(x);return {"id":x.id,"status":x.status,"title":x.title}
