from __future__ import annotations

import json

import pandas as pd
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.auth_dependencies import require_user
from app.db.models import AuditRecord, DatasetRecord, UploadRecord
from app.db.session import get_session_factory
from app.core.config import get_settings
from app.services.dataset_files import DatasetFileError, build_dataset_file_service
from app.ingestion import IngestionError, read_csv_bytes, read_csv_path
from app.profiler import profile_dataset
from app.auditor import audit_dataframe
from app.api.dependencies import get_audit_store
from app.api.routes.quality_rules import assigned_rules_for_dataset, persist_rule_executions
from app.schemas import UploadedFileInfo
from app.versioning import lineage_audits

router = APIRouter(prefix="/datasets", tags=["Datasets"])


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    domain: str = Field(default="General", max_length=120)
    owner_name: str = Field(default="Workspace team", max_length=255)
    environment: Literal["production", "staging", "archived"] = "production"
    source_type: str = Field(default="CSV", max_length=64)
    description: str | None = Field(default=None, max_length=800)
    labels: list[str] = Field(default_factory=list, max_length=12)


class DatasetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    domain: str | None = Field(default=None, max_length=120)
    owner_name: str | None = Field(default=None, max_length=255)
    environment: Literal["production", "staging", "archived"] | None = None
    source_type: str | None = Field(default=None, max_length=64)
    status: Literal["registered", "healthy", "warning", "review_needed", "archived"] | None = None
    description: str | None = Field(default=None, max_length=800)
    labels: list[str] | None = Field(default=None, max_length=12)


def serialize(row: DatasetRecord, *, latest_version: int = 0, latest_source_filename: str | None = None) -> dict:
    return {
        "id": row.id, "name": row.name, "domain": row.domain, "owner_name": row.owner_name,
        "environment": row.environment, "status": row.status, "source_type": row.source_type,
        "description": row.description, "labels": json.loads(row.labels_json or "[]"),
        "record_count": row.record_count, "column_count": row.column_count,
        "quality_score": row.quality_score, "issue_count": row.issue_count,
        "latest_audit_id": row.latest_audit_id,
        "latest_version": int(latest_version or 0),
        "latest_source_filename": latest_source_filename,
        "created_at": row.created_at, "updated_at": row.updated_at,
    }


def serialize_with_lineage(db, row: DatasetRecord) -> dict:
    audits = db.scalars(select(AuditRecord).where(
        AuditRecord.workspace_id == row.workspace_id,
        AuditRecord.dataset_name == row.name,
    ).order_by(AuditRecord.created_at.asc())).all()
    versions = lineage_audits(audits)
    source_filename = versions[-1].upload.original_filename if versions and versions[-1].upload else None
    return serialize(row, latest_version=len(versions), latest_source_filename=source_filename)


def register_audit_dataset(audit, workspace_id: int, owner_name: str = "Workspace team") -> None:
    Session = get_session_factory()
    now = datetime.now(timezone.utc)
    with Session() as db:
        row = db.scalar(select(DatasetRecord).where(DatasetRecord.workspace_id == workspace_id, DatasetRecord.name == audit.dataset_name))
        profile = audit.profile
        if row is None:
            row = DatasetRecord(workspace_id=workspace_id, name=audit.dataset_name, owner_name=owner_name,
                domain="General", environment="production", source_type="CSV", labels_json="[]", created_at=now, updated_at=now)
            db.add(row)
        row.record_count = int(getattr(profile, "row_count", 0) or 0)
        row.column_count = int(getattr(profile, "column_count", 0) or 0)
        row.quality_score = int(audit.score.overall)
        row.issue_count = sum(1 for issue in audit.issues if issue.status not in {"fixed", "resolved", "ignored"})
        row.latest_audit_id = audit.audit_id
        row.status = "healthy" if row.quality_score >= 80 else "warning" if row.quality_score >= 60 else "review_needed"
        row.updated_at = now
        db.commit()


@router.get("")
def list_datasets(search: str = Query(default=""), environment: str = Query(default="all"), user: dict = Depends(require_user)):
    wid = user["workspace"]["id"]
    Session = get_session_factory()
    with Session() as db:
        stmt = select(DatasetRecord).where(DatasetRecord.workspace_id == wid)
        if search.strip(): stmt = stmt.where(func.lower(DatasetRecord.name).contains(search.strip().lower()))
        if environment != "all": stmt = stmt.where(DatasetRecord.environment == environment)
        rows = db.scalars(stmt.order_by(DatasetRecord.updated_at.desc())).all()
        return [serialize_with_lineage(db, row) for row in rows]


@router.get("/summary")
def dataset_summary(user: dict = Depends(require_user)):
    wid = user["workspace"]["id"]
    Session = get_session_factory()
    with Session() as db:
        rows = db.scalars(select(DatasetRecord).where(DatasetRecord.workspace_id == wid)).all()
    return {
        "registered": len(rows), "monitored": sum(r.latest_audit_id is not None for r in rows),
        "active_issues": sum(r.issue_count > 0 for r in rows),
        "recently_updated": sum((datetime.now(timezone.utc) - (r.updated_at.replace(tzinfo=timezone.utc) if r.updated_at.tzinfo is None else r.updated_at)).days <= 7 for r in rows),
    }


@router.post("", status_code=201)
def create_dataset(payload: DatasetCreate, user: dict = Depends(require_user)):
    now = datetime.now(timezone.utc); wid = user["workspace"]["id"]
    row = DatasetRecord(workspace_id=wid, name=payload.name.strip(), domain=payload.domain.strip() or "General",
        owner_name=payload.owner_name.strip() or user["full_name"], environment=payload.environment,
        status="archived" if payload.environment == "archived" else "registered", source_type=payload.source_type.strip() or "CSV",
        description=payload.description, labels_json=json.dumps(sorted(set(x.strip() for x in payload.labels if x.strip()))),
        record_count=0, column_count=0, issue_count=0, created_at=now, updated_at=now)
    Session = get_session_factory()
    try:
        with Session() as db: db.add(row); db.commit(); db.refresh(row); return serialize(row)
    except IntegrityError as exc:
        raise HTTPException(409, "A dataset with this name already exists in the workspace.") from exc


@router.get("/{dataset_id}")
def get_dataset(dataset_id: int, user: dict = Depends(require_user)):
    Session = get_session_factory()
    with Session() as db:
        row = db.scalar(select(DatasetRecord).where(DatasetRecord.id == dataset_id, DatasetRecord.workspace_id == user["workspace"]["id"]))
        if row is None: raise HTTPException(404, "Dataset not found.")
        history = db.scalars(select(AuditRecord).where(AuditRecord.workspace_id == row.workspace_id, AuditRecord.dataset_name == row.name).order_by(AuditRecord.created_at.asc())).all()
        data = serialize_with_lineage(db, row); data["score_history"] = [{"score": a.score, "created_at": a.created_at} for a in history[-14:]]
        return data


@router.get("/{dataset_id}/preview")
def preview_dataset(dataset_id: int, limit: int = Query(default=10, ge=1, le=50), user: dict = Depends(require_user)):
    Session = get_session_factory()
    with Session() as db:
        row = db.scalar(select(DatasetRecord).where(DatasetRecord.id == dataset_id, DatasetRecord.workspace_id == user["workspace"]["id"]))
        if row is None:
            raise HTTPException(404, "Dataset not found.")
        if not row.latest_audit_id:
            return {"available": False, "message": "A preview becomes available after the dataset is imported and audited.", "columns": [], "rows": []}
        upload = db.scalar(select(UploadRecord).where(UploadRecord.audit_id == row.latest_audit_id))
        audit = db.scalar(select(AuditRecord).where(AuditRecord.audit_id == row.latest_audit_id, AuditRecord.workspace_id == row.workspace_id))
        if audit is None:
            return {"available": False, "message": "No completed audit is available for this dataset.", "columns": [], "rows": []}
        audit_payload = json.loads(audit.payload_json)
        stored_profile = audit_payload.get("profile", {})
        rows = []
        profile_data = stored_profile
        if upload is not None:
            files = build_dataset_file_service()
            if files.exists(upload.relative_path):
                frame = read_csv_bytes(files.read_bytes(upload.relative_path), upload.original_filename)
                profile = profile_dataset(frame)
                profile_data = profile.model_dump()
                safe = frame.head(limit)
                rows = []
                for record in safe.to_dict(orient="records"):
                    cleaned = {}
                    for key, value in record.items():
                        if value is None or (hasattr(value, "__class__") and pd.isna(value)):
                            cleaned[str(key)] = None
                        else:
                            cleaned[str(key)] = value.item() if hasattr(value, "item") else value
                    rows.append(cleaned)
        return {
            "available": True,
            "row_count": int(profile_data.get("row_count", row.record_count or 0)),
            "column_count": int(profile_data.get("column_count", row.column_count or 0)),
            "duplicate_row_count": int(profile_data.get("duplicate_row_count", 0)),
            "columns": profile_data.get("columns", []),
            "rows": rows,
            "preview_limit": limit,
        }


@router.get("/{dataset_id}/intelligence")
def dataset_intelligence(dataset_id: int, user: dict = Depends(require_user)):
    """Return the latest persisted column-intelligence profile for a dataset."""
    Session = get_session_factory()
    with Session() as db:
        row = db.scalar(select(DatasetRecord).where(
            DatasetRecord.id == dataset_id,
            DatasetRecord.workspace_id == user["workspace"]["id"],
        ))
        if row is None:
            raise HTTPException(404, "Dataset not found.")
        if not row.latest_audit_id:
            return {"available": False, "message": "Column intelligence becomes available after an audit."}
        audit = db.scalar(select(AuditRecord).where(
            AuditRecord.audit_id == row.latest_audit_id,
            AuditRecord.workspace_id == row.workspace_id,
        ))
        if audit is None:
            return {"available": False, "message": "No completed audit is available for this dataset."}
        payload = json.loads(audit.payload_json)
        profile = payload.get("profile", {})
        return {
            "available": True,
            "dataset_id": row.id,
            "dataset_name": row.name,
            "row_count": profile.get("row_count", row.record_count or 0),
            "column_count": profile.get("column_count", row.column_count or 0),
            "duplicate_row_count": profile.get("duplicate_row_count", 0),
            "duplicate_row_rate": profile.get("duplicate_row_rate", 0),
            "completeness_rate": profile.get("completeness_rate", 0),
            "high_risk_column_count": profile.get("high_risk_column_count", 0),
            "medium_risk_column_count": profile.get("medium_risk_column_count", 0),
            "columns": profile.get("columns", []),
        }


@router.get("/{dataset_id}/privacy")
def dataset_privacy(dataset_id: int, user: dict = Depends(require_user)):
    """Return sensitive-data classifications from the latest dataset profile."""
    Session = get_session_factory()
    with Session() as db:
        row = db.scalar(select(DatasetRecord).where(
            DatasetRecord.id == dataset_id,
            DatasetRecord.workspace_id == user["workspace"]["id"],
        ))
        if row is None:
            raise HTTPException(404, "Dataset not found.")
        if not row.latest_audit_id:
            return {"available": False, "message": "Privacy intelligence becomes available after an audit.", "findings": []}
        audit = db.scalar(select(AuditRecord).where(
            AuditRecord.audit_id == row.latest_audit_id,
            AuditRecord.workspace_id == row.workspace_id,
        ))
        if audit is None:
            return {"available": False, "message": "No completed audit is available for this dataset.", "findings": []}
        payload = json.loads(audit.payload_json)
        profile = payload.get("profile", {})
        findings = []
        for column in profile.get("columns", []):
            if not column.get("sensitivity"):
                continue
            findings.append({
                "column": column.get("name"),
                "classification": column.get("privacy_classification"),
                "sensitivity": column.get("sensitivity"),
                "confidence": column.get("privacy_confidence", 0),
                "reasons": column.get("privacy_reasons", []),
                "masking_recommendation": column.get("masking_recommendation"),
            })
        return {
            "available": True,
            "dataset_id": row.id,
            "dataset_name": row.name,
            "sensitive_column_count": profile.get("sensitive_column_count", len(findings)),
            "highest_sensitivity": profile.get("highest_sensitivity", "low"),
            "findings": findings,
        }


@router.patch("/{dataset_id}")
def update_dataset(dataset_id: int, payload: DatasetUpdate, user: dict = Depends(require_user)):
    Session = get_session_factory(); now = datetime.now(timezone.utc)
    with Session() as db:
        row = db.scalar(select(DatasetRecord).where(DatasetRecord.id == dataset_id, DatasetRecord.workspace_id == user["workspace"]["id"]))
        if row is None: raise HTTPException(404, "Dataset not found.")
        for field in ("name", "domain", "owner_name", "environment", "source_type", "status", "description"):
            value = getattr(payload, field)
            if value is not None: setattr(row, field, value)
        if payload.labels is not None: row.labels_json = json.dumps(sorted(set(x.strip() for x in payload.labels if x.strip())))
        row.updated_at = now; db.commit(); db.refresh(row); return serialize(row)


@router.delete("/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: int, user: dict = Depends(require_user)):
    workspace_id = int(user["workspace"]["id"])
    Session = get_session_factory()
    storage_keys: list[str] = []

    with Session() as db:
        row = db.scalar(select(DatasetRecord).where(
            DatasetRecord.id == dataset_id,
            DatasetRecord.workspace_id == workspace_id,
        ))
        if row is None:
            raise HTTPException(404, "Dataset not found.")

        audit_ids = list(db.scalars(select(AuditRecord.audit_id).where(
            AuditRecord.workspace_id == workspace_id,
            AuditRecord.dataset_name == row.name,
        )).all())
        if audit_ids:
            storage_keys = list(db.scalars(select(UploadRecord.relative_path).where(
                UploadRecord.audit_id.in_(audit_ids),
            )).all())

        db.delete(row)
        db.commit()

    files = build_dataset_file_service()
    for key in dict.fromkeys(item for item in storage_keys if item):
        try:
            files.delete(key)
        except DatasetFileError:
            # Database deletion remains authoritative; object cleanup is idempotent
            # and can be retried later by operational tooling.
            continue


def _save_version_upload(content: bytes, original_filename: str, content_type: str | None, workspace_id: int) -> UploadedFileInfo:
    return build_dataset_file_service().save_upload(content, original_filename, content_type, workspace_id, category="versions")


@router.post("/{dataset_id}/versions/import", status_code=201)
async def import_dataset_version(
    dataset_id: int,
    file: UploadFile = File(...),
    user: dict = Depends(require_user),
):
    """Import an immutable CSV revision into an existing dataset lineage and audit it automatically."""
    workspace_id = user["workspace"]["id"]
    Session = get_session_factory()
    with Session() as db:
        dataset = db.scalar(select(DatasetRecord).where(
            DatasetRecord.id == dataset_id,
            DatasetRecord.workspace_id == workspace_id,
        ))
        if dataset is None:
            raise HTTPException(404, "Dataset not found.")
        previous_audits = db.scalars(select(AuditRecord).where(
            AuditRecord.workspace_id == workspace_id,
            AuditRecord.dataset_name == dataset.name,
        ).order_by(AuditRecord.created_at.asc())).all()
        previous_count = len(lineage_audits(previous_audits))

    filename = file.filename or "dataset-version.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV dataset versions are supported.")
    upload_info: UploadedFileInfo | None = None
    try:
        content = await file.read()
        if not content:
            raise HTTPException(400, "The selected CSV file is empty.")
        upload_info = _save_version_upload(content, filename, file.content_type, int(workspace_id))
        frame = read_csv_bytes(content, filename)
        quality_rules = assigned_rules_for_dataset(workspace_id, dataset.name)
        result = audit_dataframe(frame, dataset.name, upload=upload_info, quality_rules=quality_rules)
        result.audit_kind = "version_import"
        result.dataset_version = int(previous_count) + 1
    except (IngestionError, DatasetFileError) as exc:
        if upload_info is not None:
            try:
                build_dataset_file_service().delete(upload_info.path)
            except DatasetFileError:
                pass
        raise HTTPException(400, str(exc)) from exc

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
    persisted = get_audit_store().get(result.audit_id, workspace_id)
    if persisted is None:
        raise HTTPException(500, "The version was processed but its automatic audit could not be verified.")
    version_number = int(previous_count) + 1
    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset.name,
        "version": version_number,
        "audit_id": result.audit_id,
        "audit_status": "completed",
        "audit_created_at": result.created_at,
        "source_filename": filename,
        "score": result.score.overall,
        "risk_level": result.summary.risk_level,
        "issue_count": len(result.issues),
        "row_count": result.profile.row_count,
        "column_count": result.profile.column_count,
        "message": f"Version {version_number} imported and audited.",
    }


def _version_payload(audit: AuditRecord, version: int, latest_audit_id: str | None) -> dict:
    payload = json.loads(audit.payload_json)
    profile = payload.get("profile", {})
    upload = audit.upload
    return {
        "version": version,
        "audit_id": audit.audit_id,
        "dataset_name": audit.dataset_name,
        "created_at": audit.created_at,
        "score": audit.score,
        "risk_level": audit.risk_level,
        "issue_count": audit.issue_count,
        "row_count": int(profile.get("row_count", 0)),
        "column_count": int(profile.get("column_count", 0)),
        "columns": [
            {"name": item.get("name"), "inferred_type": item.get("inferred_type"), "missing_rate": item.get("missing_rate", 0)}
            for item in profile.get("columns", [])
        ],
        "source_filename": upload.original_filename if upload else None,
        "size_bytes": upload.size_bytes if upload else None,
        "is_latest": audit.audit_id == latest_audit_id,
    }


@router.get("/{dataset_id}/versions")
def dataset_versions(dataset_id: int, user: dict = Depends(require_user)):
    """Return immutable audit-backed dataset versions for the active workspace."""
    Session = get_session_factory()
    with Session() as db:
        dataset = db.scalar(select(DatasetRecord).where(
            DatasetRecord.id == dataset_id,
            DatasetRecord.workspace_id == user["workspace"]["id"],
        ))
        if dataset is None:
            raise HTTPException(404, "Dataset not found.")
        audits = db.scalars(select(AuditRecord).where(
            AuditRecord.workspace_id == dataset.workspace_id,
            AuditRecord.dataset_name == dataset.name,
        ).order_by(AuditRecord.created_at.asc())).all()
        audits = lineage_audits(audits)
        return {
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
            "latest_audit_id": dataset.latest_audit_id,
            "version_count": len(audits),
            "versions": [_version_payload(audit, index + 1, dataset.latest_audit_id) for index, audit in enumerate(audits)],
        }


@router.get("/{dataset_id}/versions/compare")
def compare_dataset_versions(
    dataset_id: int,
    baseline_audit_id: str = Query(...),
    candidate_audit_id: str = Query(...),
    user: dict = Depends(require_user),
):
    """Compare two versions only when both belong to the requested dataset and active workspace."""
    from app.comparison import compare_audits
    from app.api.dependencies import get_audit_store

    Session = get_session_factory()
    wid = user["workspace"]["id"]
    with Session() as db:
        dataset = db.scalar(select(DatasetRecord).where(DatasetRecord.id == dataset_id, DatasetRecord.workspace_id == wid))
        if dataset is None:
            raise HTTPException(404, "Dataset not found.")
        rows = db.scalars(select(AuditRecord).where(
            AuditRecord.workspace_id == wid,
            AuditRecord.dataset_name == dataset.name,
            AuditRecord.audit_id.in_([baseline_audit_id, candidate_audit_id]),
        )).all()
        if len(rows) != 2:
            raise HTTPException(404, "One or both dataset versions are not available in the active workspace.")
    store = get_audit_store()
    baseline = store.get(baseline_audit_id, wid)
    candidate = store.get(candidate_audit_id, wid)
    if baseline is None or candidate is None:
        raise HTTPException(404, "One or both dataset versions are not available in the active workspace.")
    comparison = compare_audits(baseline, candidate)
    return jsonable_encoder(comparison)
