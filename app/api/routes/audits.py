from __future__ import annotations

import json
from datetime import UTC
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import ValidationError
from sqlalchemy import select

from app.analyst import answer_question
from app.api.auth_dependencies import require_user
from app.api.dependencies import get_audit_store
from app.api.routes.datasets import register_audit_dataset
from app.api.routes.quality_rules import assigned_rules_for_dataset, persist_rule_executions
from app.auditor import audit_dataframe
from app.comparison import compare_audits
from app.contracts import generate_contract
from app.core.config import get_settings
from app.db.models import AuditRecord, UploadRecord
from app.db.session import get_session_factory
from app.ingestion import IngestionError, read_csv_bytes, read_csv_path
from app.issue_lifecycle import list_activities, record_activity
from app.jobs.runtime import get_dispatcher
from app.jobs.service import create_job, serialise_job
from app.jobs.types import JobType
from app.ml_readiness import assess_ml_readiness
from app.remediation import apply_remediation_actions, build_remediation_plan
from app.reports import build_html_report, build_markdown_report
from app.schemas import (
    AnalystAnswer,
    AnalystQuestion,
    AppliedRecommendation,
    AuditComparison,
    AuditListItem,
    AuditResult,
    AuditRuleConfig,
    DataContract,
    IssueCommentCreate,
    IssueLifecycleDetail,
    IssueStatusUpdate,
    MlReadiness,
    QualityIssue,
    RemediationApplyResult,
    RemediationPlan,
    RemediationPreview,
    RemediationRequest,
    ScoreRecalculationRequest,
    UploadedFileInfo,
)
from app.scoring import score_audit
from app.services.dataset_files import DatasetFileError, build_dataset_file_service
from app.summaries import summarize_audit

router = APIRouter(prefix="/audits", tags=["Audits"])


def load_audit(audit_id: str, workspace_id: int | None = None) -> AuditResult:
    result = get_audit_store().get(audit_id, workspace_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Audit not found.")
    return result


def parse_rule_config(raw_rules: str | None) -> AuditRuleConfig:
    if raw_rules is None or not raw_rules.strip():
        return AuditRuleConfig()
    try:
        payload = json.loads(raw_rules)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="rules_json must be valid JSON.") from exc
    return AuditRuleConfig.model_validate(payload)


def save_upload(
    content: bytes, original_filename: str, content_type: str | None, workspace_id: int
) -> UploadedFileInfo:
    return build_dataset_file_service().save_upload(content, original_filename, content_type, workspace_id)


def _utc_datetime(value):
    """Return one canonical UTC instant for SQLite and timezone-aware values."""
    if value is None:
        return value
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _normalise_audit_time(audit: AuditResult) -> AuditResult:
    audit.created_at = _utc_datetime(audit.created_at)
    return audit


@router.get("", response_model=list[AuditListItem])
def list_audits(user: dict[str, object] = Depends(require_user)) -> list[AuditListItem]:
    rows = get_audit_store().list(user["workspace"]["id"])
    for row in rows:
        row.created_at = _utc_datetime(row.created_at)
    return jsonable_encoder(rows)


@router.post("/upload/async", status_code=202)
async def upload_audit_async(
    file: UploadFile = File(...),
    rules_json: str | None = Form(default=None),
    user: dict[str, object] = Depends(require_user),
):
    """Persist an upload, queue its audit, and return immediately with a trackable job."""
    workspace_id = int(user["workspace"]["id"])
    content = await file.read()
    upload_info: UploadedFileInfo | None = None
    try:
        rule_config = parse_rule_config(rules_json)
        upload_info = save_upload(content, file.filename or "uploaded.csv", file.content_type, workspace_id)
        # Validate CSV synchronously so malformed uploads fail before a job is created.
        read_csv_bytes(content, file.filename or "uploaded.csv")
    except (IngestionError, DatasetFileError) as exc:
        if upload_info is not None:
            build_dataset_file_service().delete(upload_info.path)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValidationError as exc:
        if upload_info is not None:
            build_dataset_file_service().delete(upload_info.path)
        raise HTTPException(status_code=400, detail=json.loads(exc.json())) from exc

    idempotency_key = f"dataset-audit:{workspace_id}:{upload_info.checksum_sha256 or uuid4()}"
    job, created = create_job(
        workspace_id=workspace_id,
        created_by_user_id=int(user["id"]),
        job_type=JobType.DATASET_AUDIT,
        idempotency_key=idempotency_key,
        payload={
            "storage_key": upload_info.path,
            "filename": file.filename or "uploaded.csv",
            "content_type": file.content_type,
            "upload": upload_info.model_dump(mode="json"),
            "rule_config": rule_config.model_dump(mode="json"),
            "owner_name": str(user.get("full_name") or "Workspace team"),
            "audit_kind": "dataset_import",
            "dataset_version": 1,
        },
    )
    if created:
        get_dispatcher().enqueue(job.id, idempotency_key=job.idempotency_key)
    elif upload_info.path != json.loads(job.payload_json or "{}").get("storage_key"):
        # An idempotent duplicate does not need a second stored copy.
        build_dataset_file_service().delete(upload_info.path)
    return serialise_job(job)


@router.post("/upload", response_model=AuditResult)
async def upload_audit(
    file: UploadFile = File(...),
    rules_json: str | None = Form(default=None),
    user: dict[str, object] = Depends(require_user),
) -> AuditResult:
    workspace_id = int(user["workspace"]["id"])
    upload_info: UploadedFileInfo | None = None
    try:
        content = await file.read()
        rule_config = parse_rule_config(rules_json)
        upload_info = save_upload(content, file.filename or "uploaded.csv", file.content_type, workspace_id)
        frame = read_csv_bytes(content, file.filename or "uploaded.csv")
        quality_rules = assigned_rules_for_dataset(workspace_id, file.filename or "uploaded.csv")
        result = audit_dataframe(
            frame,
            file.filename or "uploaded.csv",
            rule_config=rule_config,
            upload=upload_info,
            quality_rules=quality_rules,
        )
        result.audit_kind = "dataset_import"
        result.dataset_version = 1
    except (IngestionError, DatasetFileError) as exc:
        if upload_info is not None:
            try:
                build_dataset_file_service().delete(upload_info.path)
            except DatasetFileError:
                pass
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValidationError as exc:
        if upload_info is not None:
            try:
                build_dataset_file_service().delete(upload_info.path)
            except DatasetFileError:
                pass
        raise HTTPException(status_code=400, detail=json.loads(exc.json())) from exc

    try:
        get_audit_store().save(result, workspace_id)
        persist_rule_executions(result.audit_id, result.rule_executions)
        register_audit_dataset(result, workspace_id, str(user.get("full_name") or "Workspace team"))
    except Exception:
        if upload_info is not None:
            try:
                build_dataset_file_service().delete(upload_info.path)
            except DatasetFileError:
                pass
        raise
    return jsonable_encoder(result)


@router.post("/{audit_id}/rerun", response_model=AuditResult)
def rerun_audit(audit_id: str, user: dict[str, object] = Depends(require_user)) -> AuditResult:
    """Run a fresh audit using the selected audit's persisted source dataset."""
    workspace_id = user["workspace"]["id"]
    source_audit = load_audit(audit_id, workspace_id)
    Session = get_session_factory()
    with Session() as db:
        audit_record = db.scalar(
            select(AuditRecord).where(
                AuditRecord.audit_id == audit_id,
                AuditRecord.workspace_id == workspace_id,
            )
        )
        upload_record = db.scalar(select(UploadRecord).where(UploadRecord.audit_id == audit_id))

    if audit_record is None:
        raise HTTPException(status_code=404, detail="Audit not found.")

    try:
        if upload_record is not None:
            files = build_dataset_file_service()
            if not files.exists(upload_record.relative_path):
                raise HTTPException(status_code=409, detail="The source file for this audit is no longer available.")
            content = files.read_bytes(upload_record.relative_path)
            upload_info = save_upload(
                content, upload_record.original_filename, upload_record.content_type, int(workspace_id)
            )
            frame = read_csv_bytes(content, upload_record.original_filename)
        elif source_audit.dataset_name == get_settings().sample_dataset.name:
            source_path = get_settings().sample_dataset
            content = source_path.read_bytes()
            upload_info = save_upload(content, source_path.name, "text/csv", int(workspace_id))
            frame = read_csv_path(source_path)
        else:
            raise HTTPException(status_code=409, detail="This dataset has no persisted source file to rerun.")

        quality_rules = assigned_rules_for_dataset(workspace_id, source_audit.dataset_name)
        result = audit_dataframe(
            frame,
            source_audit.dataset_name,
            rule_config=source_audit.rule_config,
            upload=upload_info,
            quality_rules=quality_rules,
        )
        result.audit_kind = "rerun"
        result.dataset_version = source_audit.dataset_version
    except IngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    get_audit_store().save(result, workspace_id)
    persist_rule_executions(result.audit_id, result.rule_executions)
    register_audit_dataset(result, workspace_id, str(user.get("full_name") or "Workspace team"))
    return jsonable_encoder(result)


@router.post("/sample", response_model=AuditResult)
def sample_audit(user: dict[str, object] = Depends(require_user)) -> AuditResult:
    try:
        frame = read_csv_path(get_settings().sample_dataset)
    except IngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    quality_rules = assigned_rules_for_dataset(user["workspace"]["id"], get_settings().sample_dataset.name)
    result = audit_dataframe(frame, get_settings().sample_dataset.name, quality_rules=quality_rules)
    result.audit_kind = "sample"
    result.dataset_version = 1
    get_audit_store().save(result, user["workspace"]["id"])
    persist_rule_executions(result.audit_id, result.rule_executions)
    register_audit_dataset(result, user["workspace"]["id"], str(user.get("full_name") or "Workspace team"))
    return jsonable_encoder(result)


@router.post("/sample/configured", response_model=AuditResult)
def configured_sample_audit(config: AuditRuleConfig, user: dict[str, object] = Depends(require_user)) -> AuditResult:
    frame = read_csv_path(get_settings().sample_dataset)
    quality_rules = assigned_rules_for_dataset(user["workspace"]["id"], get_settings().sample_dataset.name)
    result = audit_dataframe(frame, get_settings().sample_dataset.name, rule_config=config, quality_rules=quality_rules)
    result.audit_kind = "sample"
    result.dataset_version = 1
    get_audit_store().save(result, user["workspace"]["id"])
    persist_rule_executions(result.audit_id, result.rule_executions)
    register_audit_dataset(result, user["workspace"]["id"], str(user.get("full_name") or "Workspace team"))
    return jsonable_encoder(result)


@router.get("/compare/{baseline_audit_id}/{candidate_audit_id}", response_model=AuditComparison)
def compare_saved_audits(
    baseline_audit_id: str, candidate_audit_id: str, user: dict[str, object] = Depends(require_user)
) -> AuditComparison:
    wid = user["workspace"]["id"]
    return jsonable_encoder(compare_audits(load_audit(baseline_audit_id, wid), load_audit(candidate_audit_id, wid)))


@router.get("/{audit_id}", response_model=AuditResult)
def get_audit(audit_id: str, user: dict[str, object] = Depends(require_user)) -> AuditResult:
    return jsonable_encoder(_normalise_audit_time(load_audit(audit_id, user["workspace"]["id"])))


@router.get("/{audit_id}/issues", response_model=list[QualityIssue])
def get_issues(audit_id: str, user: dict[str, object] = Depends(require_user)) -> list[QualityIssue]:
    return jsonable_encoder(load_audit(audit_id, user["workspace"]["id"]).issues)


@router.post("/{audit_id}/issues/{issue_id}/apply-recommendation", response_model=AppliedRecommendation)
def apply_issue_recommendation(
    audit_id: str, issue_id: str, user: dict[str, object] = Depends(require_user)
) -> AppliedRecommendation:
    result = load_audit(audit_id, user["workspace"]["id"])
    issue = next((item for item in result.issues if item.id == issue_id), None)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found.")
    if issue.status == "fixed":
        raise HTTPException(status_code=409, detail="This recommendation has already been applied.")
    if issue.category == "privacy" and not (issue.resolution_note and issue.resolution_evidence):
        raise HTTPException(
            status_code=409,
            detail=(
                "Privacy findings cannot be resolved automatically. Record the implemented privacy control "
                "in the resolution note and provide validation evidence before applying the recommendation."
            ),
        )

    previous_score = result.score.overall
    issue.status = "fixed"
    issue.owner = str(user.get("full_name") or "Workspace team")
    if issue.category != "privacy":
        issue.resolution_note = f"Applied recommendation: {issue.recommendation}"
    issue.affected_rows = 0
    issue.affected_rate = 0.0

    result.score = score_audit(result.profile, result.issues, result.scoring_context)
    result.summary = summarize_audit(result.profile, result.issues, result.score)
    get_audit_store().save(result, user["workspace"]["id"])
    record_activity(
        audit_id=audit_id,
        issue_id=issue_id,
        workspace_id=user["workspace"]["id"],
        actor_user_id=int(user["id"]),
        actor_name=str(user.get("full_name") or user.get("email")),
        action="recommendation_applied",
        field_name="status",
        previous_value="open",
        new_value="fixed",
        note=issue.resolution_note,
    )

    return jsonable_encoder(
        AppliedRecommendation(
            audit_id=result.audit_id,
            issue_id=issue.id,
            previous_score=previous_score,
            updated_score=result.score.overall,
            score_improvement=result.score.overall - previous_score,
            resolution_note=issue.resolution_note,
            audit=result,
        )
    )


@router.patch("/{audit_id}/issues/{issue_id}", response_model=AuditResult)
def update_issue_status(
    audit_id: str, issue_id: str, update: IssueStatusUpdate, user: dict[str, object] = Depends(require_user)
) -> AuditResult:
    workspace_id = user["workspace"]["id"]
    result = load_audit(audit_id, workspace_id)
    issue = next((item for item in result.issues if item.id == issue_id), None)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found.")

    changes = update.model_dump(exclude_none=True)
    if not changes:
        return jsonable_encoder(result)
    if changes.get("status") in {"resolved", "fixed"} and not (changes.get("resolution_note") or issue.resolution_note):
        raise HTTPException(status_code=400, detail="A resolution note is required when resolving an issue.")

    actor_name = str(user.get("full_name") or user.get("email") or "Workspace user")
    for field_name, value in changes.items():
        previous = getattr(issue, field_name, None)
        if previous == value:
            continue
        setattr(issue, field_name, value)
        record_activity(
            audit_id=audit_id,
            issue_id=issue_id,
            workspace_id=workspace_id,
            actor_user_id=int(user["id"]),
            actor_name=actor_name,
            action="field_updated",
            field_name=field_name,
            previous_value=previous,
            new_value=value,
        )
    issue.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    if issue.status == "reopened":
        issue.status = "open"
        record_activity(
            audit_id=audit_id,
            issue_id=issue_id,
            workspace_id=workspace_id,
            actor_user_id=int(user["id"]),
            actor_name=actor_name,
            action="reopened",
            field_name="status",
            new_value="open",
        )

    result.score = score_audit(result.profile, result.issues, result.scoring_context)
    result.summary = summarize_audit(result.profile, result.issues, result.score)
    get_audit_store().save(result, workspace_id)
    register_audit_dataset(result, workspace_id, actor_name)
    return jsonable_encoder(result)


@router.get("/{audit_id}/issues/{issue_id}/lifecycle", response_model=IssueLifecycleDetail)
def get_issue_lifecycle(
    audit_id: str, issue_id: str, user: dict[str, object] = Depends(require_user)
) -> IssueLifecycleDetail:
    workspace_id = user["workspace"]["id"]
    result = load_audit(audit_id, workspace_id)
    issue = next((item for item in result.issues if item.id == issue_id), None)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found.")
    return jsonable_encoder(
        IssueLifecycleDetail(issue=issue, activities=list_activities(audit_id, issue_id, workspace_id))
    )


@router.post("/{audit_id}/issues/{issue_id}/comments", response_model=IssueLifecycleDetail)
def add_issue_comment(
    audit_id: str, issue_id: str, comment: IssueCommentCreate, user: dict[str, object] = Depends(require_user)
) -> IssueLifecycleDetail:
    workspace_id = user["workspace"]["id"]
    result = load_audit(audit_id, workspace_id)
    issue = next((item for item in result.issues if item.id == issue_id), None)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found.")
    record_activity(
        audit_id=audit_id,
        issue_id=issue_id,
        workspace_id=workspace_id,
        actor_user_id=int(user["id"]),
        actor_name=str(user.get("full_name") or user.get("email")),
        action="comment_added",
        note=comment.body.strip(),
    )
    return jsonable_encoder(
        IssueLifecycleDetail(issue=issue, activities=list_activities(audit_id, issue_id, workspace_id))
    )


@router.get("/{audit_id}/score-breakdown")
def get_score_breakdown(audit_id: str, user: dict[str, object] = Depends(require_user)) -> dict[str, object]:
    result = load_audit(audit_id, user["workspace"]["id"])
    return jsonable_encoder(
        {
            "audit_id": result.audit_id,
            "dataset_name": result.dataset_name,
            "score": result.score,
            "scoring_context": result.scoring_context,
            "top_deductions": result.score.deductions[:10],
        }
    )


@router.post("/{audit_id}/score/recalculate", response_model=AuditResult)
def recalculate_score(
    audit_id: str, update: ScoreRecalculationRequest, user: dict[str, object] = Depends(require_user)
) -> AuditResult:
    result = load_audit(audit_id, user["workspace"]["id"])
    payload = result.scoring_context.model_dump()
    for key, value in update.model_dump(exclude_none=True).items():
        payload[key] = value
    result.scoring_context = type(result.scoring_context).model_validate(payload)
    result.score = score_audit(result.profile, result.issues, result.scoring_context)
    result.summary = summarize_audit(result.profile, result.issues, result.score)
    get_audit_store().save(result, user["workspace"]["id"])
    register_audit_dataset(result, user["workspace"]["id"], str(user.get("full_name") or "Workspace team"))
    return jsonable_encoder(result)


@router.get("/{audit_id}/report")
def get_report(audit_id: str, user: dict[str, object] = Depends(require_user)) -> dict[str, object]:
    result = load_audit(audit_id, user["workspace"]["id"])
    return {
        "dataset": result.dataset_name,
        "quality_score": result.score.overall,
        "risk_level": result.summary.risk_level,
        "executive_summary": result.summary.executive_summary,
        "recommended_focus": result.summary.recommended_focus,
        "issue_count": sum(1 for issue in result.issues if issue.status not in {"fixed", "resolved", "ignored"}),
        "critical_or_high_issues": [i.model_dump() for i in result.issues if i.severity in {"critical", "high"}],
    }


@router.get("/{audit_id}/report.md", response_class=PlainTextResponse)
def get_markdown_report(audit_id: str, user: dict[str, object] = Depends(require_user)) -> str:
    return build_markdown_report(load_audit(audit_id, user["workspace"]["id"]))


@router.get("/{audit_id}/report.html", response_class=HTMLResponse)
def get_html_report(audit_id: str, user: dict[str, object] = Depends(require_user)) -> str:
    return build_html_report(load_audit(audit_id, user["workspace"]["id"]))


@router.get("/{audit_id}/remediation", response_model=RemediationPlan)
def get_remediation(audit_id: str, user: dict[str, object] = Depends(require_user)) -> RemediationPlan:
    return jsonable_encoder(build_remediation_plan(load_audit(audit_id, user["workspace"]["id"])))


def _audit_source_frame(audit_id: str, workspace_id: int):
    with get_session_factory()() as session:
        record = session.scalar(
            select(AuditRecord).where(AuditRecord.audit_id == audit_id, AuditRecord.workspace_id == workspace_id)
        )
        if record is None or record.upload is None:
            raise HTTPException(status_code=404, detail="Source dataset is not available for this audit.")
        storage_key = record.upload.relative_path
        original_filename = record.upload.original_filename
    files = build_dataset_file_service()
    if not files.exists(storage_key):
        raise HTTPException(status_code=404, detail="Source dataset file is missing.")
    try:
        return read_csv_bytes(files.read_bytes(storage_key), original_filename)
    except (DatasetFileError, IngestionError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{audit_id}/remediation/preview", response_model=RemediationPreview)
def preview_remediation(
    audit_id: str, request: RemediationRequest, user: dict[str, object] = Depends(require_user)
) -> RemediationPreview:
    workspace_id = user["workspace"]["id"]
    audit = load_audit(audit_id, workspace_id)
    frame = _audit_source_frame(audit_id, workspace_id)
    corrected, stats = apply_remediation_actions(
        frame, audit, request.issue_ids, request.fill_strategy, request.mask_sensitive
    )
    quality_rules = assigned_rules_for_dataset(workspace_id, audit.dataset_name)
    projected = audit_dataframe(
        corrected, audit.dataset_name, quality_rules=quality_rules, scoring_context=audit.scoring_context
    )
    return jsonable_encoder(
        RemediationPreview(
            audit_id=audit_id,
            selected_actions=len(request.issue_ids),
            rows_before=len(frame),
            rows_after=len(corrected),
            columns_before=len(frame.columns),
            columns_after=len(corrected.columns),
            score_before=audit.score.overall,
            projected_score=projected.score.overall,
            projected_score_delta=projected.score.overall - audit.score.overall,
            issues_before=len([i for i in audit.issues if i.status not in {"fixed", "resolved", "ignored"}]),
            projected_issues=len([i for i in projected.issues if i.status not in {"fixed", "resolved", "ignored"}]),
            **stats,
        )
    )


@router.post("/{audit_id}/remediation/apply", response_model=RemediationApplyResult)
def apply_remediation(
    audit_id: str, request: RemediationRequest, user: dict[str, object] = Depends(require_user)
) -> RemediationApplyResult:
    workspace_id = user["workspace"]["id"]
    audit = load_audit(audit_id, workspace_id)
    frame = _audit_source_frame(audit_id, workspace_id)
    corrected, stats = apply_remediation_actions(
        frame, audit, request.issue_ids, request.fill_strategy, request.mask_sensitive
    )
    cleaned_name = f"cleaned_{audit.dataset_name}"
    csv_content = corrected.to_csv(index=False).encode("utf-8")
    upload_info = save_upload(csv_content, cleaned_name, "text/csv", int(workspace_id))
    try:
        quality_rules = assigned_rules_for_dataset(workspace_id, audit.dataset_name)
        corrected_audit = audit_dataframe(
            corrected,
            cleaned_name,
            upload=upload_info,
            quality_rules=quality_rules,
            scoring_context=audit.scoring_context,
        )
        get_audit_store().save(corrected_audit, workspace_id)
        register_audit_dataset(corrected_audit, workspace_id, str(user.get("full_name") or "Workspace team"))
        persist_rule_executions(corrected_audit.audit_id, corrected_audit.rule_executions)
    except Exception:
        try:
            build_dataset_file_service().delete(upload_info.path)
        except DatasetFileError:
            pass
        raise
    return jsonable_encoder(
        RemediationApplyResult(
            source_audit_id=audit_id,
            corrected_audit=corrected_audit,
            download_url=f"/audits/{corrected_audit.audit_id}/source.csv",
            applied_actions=len(request.issue_ids),
            changed_cells=stats["changed_cells"],
            removed_rows=stats["removed_rows"],
        )
    )


@router.get("/{audit_id}/source.csv", response_class=PlainTextResponse)
def download_audit_source(audit_id: str, user: dict[str, object] = Depends(require_user)):
    workspace_id = user["workspace"]["id"]
    load_audit(audit_id, workspace_id)
    with get_session_factory()() as session:
        record = session.scalar(
            select(AuditRecord).where(AuditRecord.audit_id == audit_id, AuditRecord.workspace_id == workspace_id)
        )
        if record is None or record.upload is None:
            raise HTTPException(status_code=404, detail="Source dataset is not available.")
        storage_key = record.upload.relative_path
        filename = record.upload.original_filename
    files = build_dataset_file_service()
    if not files.exists(storage_key):
        raise HTTPException(status_code=404, detail="Source dataset file is missing.")
    return PlainTextResponse(
        files.read_bytes(storage_key),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{audit_id}/contract", response_model=DataContract)
def get_data_contract(audit_id: str, user: dict[str, object] = Depends(require_user)) -> DataContract:
    workspace_id = user["workspace"]["id"]
    audit = load_audit(audit_id, workspace_id)
    assigned_rules = assigned_rules_for_dataset(workspace_id, audit.dataset_name)
    return jsonable_encoder(generate_contract(audit, assigned_rules))


@router.get("/{audit_id}/ml-readiness", response_model=MlReadiness)
def get_ml_readiness(audit_id: str, user: dict[str, object] = Depends(require_user)) -> MlReadiness:
    return jsonable_encoder(assess_ml_readiness(load_audit(audit_id, user["workspace"]["id"])))


@router.post("/{audit_id}/analyst", response_model=AnalystAnswer)
def ask_analyst(
    audit_id: str, question: AnalystQuestion, user: dict[str, object] = Depends(require_user)
) -> AnalystAnswer:
    return jsonable_encoder(
        answer_question(load_audit(audit_id, user["workspace"]["id"]), question.question, question.history)
    )


@router.post("/{audit_id}/summary/regenerate", response_model=AuditResult)
def regenerate_summary(audit_id: str, user: dict[str, object] = Depends(require_user)) -> AuditResult:
    result = load_audit(audit_id, user["workspace"]["id"])
    result.summary = summarize_audit(result.profile, result.issues, result.score)
    get_audit_store().save(result, user["workspace"]["id"])
    return jsonable_encoder(result)
