from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app.analyst import answer_question
from app.auditor import audit_dataframe
from app.comparison import compare_audits
from app.contracts import generate_contract
from app.ingestion import IngestionError, read_csv_bytes, read_csv_path
from app.ml_readiness import assess_ml_readiness
from app.reports import build_html_report, build_markdown_report
from app.remediation import build_remediation_plan
from app.schemas import (
    AnalystAnswer,
    AnalystQuestion,
    AuditComparison,
    AuditListItem,
    AuditResult,
    AuditRuleConfig,
    DataContract,
    IssueStatusUpdate,
    MlReadiness,
    QualityIssue,
    RemediationPlan,
    UploadedFileInfo,
)
from app.storage import AuditStore
from app.summaries import summarize_audit


ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DATASET = ROOT / "samples" / "customers_dirty.csv"
AUDIT_STORE = AuditStore(ROOT / "data" / "audits")
UPLOAD_ROOT = ROOT / "data" / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AI Data Quality Auditor", version="0.1.0")
app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-data-quality-auditor"}


def load_audit(audit_id: str) -> AuditResult:
    result = AUDIT_STORE.get(audit_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Audit not found.")
    return result


@app.get("/audits", response_model=list[AuditListItem])
def list_audits() -> list[AuditListItem]:
    return jsonable_encoder(AUDIT_STORE.list())


@app.post("/audits/upload", response_model=AuditResult)
async def upload_audit(
    file: UploadFile = File(...),
    rules_json: str | None = Form(default=None),
) -> AuditResult:
    try:
        content = await file.read()
        rule_config = parse_rule_config(rules_json)
        upload_info = save_upload(content, file.filename or "uploaded.csv", file.content_type)
        frame = read_csv_bytes(content, file.filename or "uploaded.csv")
        result = audit_dataframe(
            frame,
            file.filename or "uploaded.csv",
            rule_config=rule_config,
            upload=upload_info,
        )
    except IngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=json.loads(exc.json())) from exc

    AUDIT_STORE.save(result)
    return jsonable_encoder(result)


@app.post("/audits/sample", response_model=AuditResult)
def sample_audit() -> AuditResult:
    try:
        frame = read_csv_path(SAMPLE_DATASET)
    except IngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = audit_dataframe(frame, SAMPLE_DATASET.name)
    AUDIT_STORE.save(result)
    return jsonable_encoder(result)


@app.post("/audits/sample/configured", response_model=AuditResult)
def configured_sample_audit(config: AuditRuleConfig) -> AuditResult:
    try:
        frame = read_csv_path(SAMPLE_DATASET)
    except IngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = audit_dataframe(frame, SAMPLE_DATASET.name, rule_config=config)
    AUDIT_STORE.save(result)
    return jsonable_encoder(result)


@app.get("/audits/{audit_id}", response_model=AuditResult)
def get_audit(audit_id: str) -> AuditResult:
    return jsonable_encoder(load_audit(audit_id))


@app.get("/audits/{audit_id}/issues", response_model=list[QualityIssue])
def get_issues(audit_id: str) -> list[QualityIssue]:
    return jsonable_encoder(load_audit(audit_id).issues)


@app.patch("/audits/{audit_id}/issues/{issue_id}", response_model=AuditResult)
def update_issue_status(audit_id: str, issue_id: str, update: IssueStatusUpdate) -> AuditResult:
    result = load_audit(audit_id)
    for issue in result.issues:
        if issue.id == issue_id:
            issue.status = update.status
            issue.owner = update.owner
            issue.resolution_note = update.resolution_note
            AUDIT_STORE.save(result)
            return jsonable_encoder(result)
    raise HTTPException(status_code=404, detail="Issue not found.")


@app.get("/audits/{audit_id}/report")
def get_report(audit_id: str) -> dict[str, object]:
    result = load_audit(audit_id)
    return {
        "dataset": result.dataset_name,
        "quality_score": result.score.overall,
        "risk_level": result.summary.risk_level,
        "executive_summary": result.summary.executive_summary,
        "recommended_focus": result.summary.recommended_focus,
        "issue_count": len(result.issues),
        "critical_or_high_issues": [
            issue.model_dump() for issue in result.issues if issue.severity in {"critical", "high"}
        ],
    }


@app.get("/audits/{audit_id}/report.md", response_class=PlainTextResponse)
def get_markdown_report(audit_id: str) -> str:
    return build_markdown_report(load_audit(audit_id))


@app.get("/audits/{audit_id}/report.html", response_class=HTMLResponse)
def get_html_report(audit_id: str) -> str:
    return build_html_report(load_audit(audit_id))


@app.get("/audits/{audit_id}/remediation", response_model=RemediationPlan)
def get_remediation(audit_id: str) -> RemediationPlan:
    return jsonable_encoder(build_remediation_plan(load_audit(audit_id)))


@app.get("/audits/{audit_id}/contract", response_model=DataContract)
def get_data_contract(audit_id: str) -> DataContract:
    return jsonable_encoder(generate_contract(load_audit(audit_id)))


@app.get("/audits/{audit_id}/ml-readiness", response_model=MlReadiness)
def get_ml_readiness(audit_id: str) -> MlReadiness:
    return jsonable_encoder(assess_ml_readiness(load_audit(audit_id)))


@app.get("/audits/compare/{baseline_audit_id}/{candidate_audit_id}", response_model=AuditComparison)
def compare_saved_audits(baseline_audit_id: str, candidate_audit_id: str) -> AuditComparison:
    return jsonable_encoder(compare_audits(load_audit(baseline_audit_id), load_audit(candidate_audit_id)))


@app.post("/audits/{audit_id}/analyst", response_model=AnalystAnswer)
def ask_analyst(audit_id: str, question: AnalystQuestion) -> AnalystAnswer:
    return jsonable_encoder(answer_question(load_audit(audit_id), question.question, question.history))


@app.post("/audits/{audit_id}/summary/regenerate", response_model=AuditResult)
def regenerate_summary(audit_id: str) -> AuditResult:
    result = load_audit(audit_id)
    result.summary = summarize_audit(result.profile, result.issues, result.score)
    AUDIT_STORE.save(result)
    return jsonable_encoder(result)


def parse_rule_config(raw_rules: str | None) -> AuditRuleConfig:
    if raw_rules is None or not raw_rules.strip():
        return AuditRuleConfig()
    try:
        payload = json.loads(raw_rules)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="rules_json must be valid JSON.") from exc
    return AuditRuleConfig.model_validate(payload)


def save_upload(content: bytes, original_filename: str, content_type: str | None) -> UploadedFileInfo:
    extension = Path(original_filename).suffix.lower() or ".csv"
    stored_filename = f"{uuid4()}{extension}"
    path = UPLOAD_ROOT / stored_filename
    path.write_bytes(content)
    return UploadedFileInfo(
        original_filename=original_filename,
        stored_filename=stored_filename,
        path=str(path.relative_to(ROOT)),
        size_bytes=len(content),
        content_type=content_type,
    )
