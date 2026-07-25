from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, select, func
from sqlalchemy.exc import IntegrityError

from app.api.auth_dependencies import require_roles, require_user
from app.db.models import AuditRecord, DataContractRecord, DatasetRecord, DatasetRuleAssignmentRecord, QualityRuleRecord, RuleExecutionRecord, UploadRecord
from app.db.session import get_session_factory
from app.schemas import AuditResult, DataContract, RuleDefinition
from pydantic import BaseModel, Field
from app.contracts import generate_contract
from app.core.config import get_settings
from app.ingestion import read_csv_path
from app.versioning import lineage_audits
from app.quality_rules import execute_quality_rules

router = APIRouter(prefix="/quality-rules", tags=["Quality Rules"])


class ContractPayload(BaseModel):
    dataset_id: int
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=800)
    status: str = Field(default="draft", pattern="^(draft|published|archived)$")
    contract: dict = Field(default_factory=dict)


class ContractStatusPayload(BaseModel):
    status: str = Field(pattern="^(draft|published|archived)$")


class BulkAssignmentPayload(BaseModel):
    rule_ids: list[int] = Field(min_length=1)
    dataset_ids: list[int] = Field(min_length=1)
    action: str = Field(default="assign", pattern="^(assign|unassign)$")


def _serialize_contract(row: DataContractRecord, dataset_name: str | None = None) -> dict:
    return {
        "id": row.id, "contract_key": row.contract_key, "workspace_id": row.workspace_id,
        "dataset_id": row.dataset_id, "dataset_name": dataset_name, "name": row.name,
        "description": row.description, "status": row.status, "version": row.version,
        "contract": json.loads(row.contract_json or "{}"), "source_audit_id": row.source_audit_id,
        "validation_status": row.validation_status,
        "validation": json.loads(row.validation_json or "{}"), "validated_at": row.validated_at,
        "published_at": row.published_at, "created_at": row.created_at, "updated_at": row.updated_at,
    }


def _serialize(row: QualityRuleRecord) -> dict:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "name": row.name,
        "description": row.description,
        "rule_type": row.rule_type,
        "scope": row.scope,
        "column_name": row.column_name,
        "category": row.category,
        "severity": row.severity,
        "parameters": json.loads(row.parameters_json or "{}"),
        "recommendation": row.recommendation,
        "is_active": bool(row.is_active),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def assigned_rules_for_dataset(workspace_id: int, dataset_name: str) -> list[RuleDefinition]:
    Session = get_session_factory()
    with Session() as db:
        dataset = db.scalar(select(DatasetRecord).where(
            DatasetRecord.workspace_id == workspace_id,
            DatasetRecord.name == dataset_name,
        ))
        if dataset is None:
            return []
        rows = db.scalars(
            select(QualityRuleRecord)
            .join(DatasetRuleAssignmentRecord, DatasetRuleAssignmentRecord.rule_id == QualityRuleRecord.id)
            .where(
                DatasetRuleAssignmentRecord.dataset_id == dataset.id,
                DatasetRuleAssignmentRecord.is_active == 1,
                QualityRuleRecord.workspace_id == workspace_id,
                QualityRuleRecord.is_active == 1,
            )
            .order_by(QualityRuleRecord.id)
        ).all()
        return [RuleDefinition.model_validate(_serialize(row)) for row in rows]


def persist_rule_executions(audit_id: str, executions: list) -> None:
    if not executions:
        return
    Session = get_session_factory()
    with Session() as db:
        db.execute(delete(RuleExecutionRecord).where(RuleExecutionRecord.audit_id == audit_id))
        for execution in executions:
            db.add(RuleExecutionRecord(
                audit_id=audit_id,
                rule_id=execution.rule_id,
                outcome=execution.outcome,
                affected_rows=execution.affected_rows,
                affected_rate=execution.affected_rate,
                message=execution.message,
                executed_at=execution.executed_at,
            ))
        db.commit()


@router.get("")
def list_rules(user: dict = Depends(require_user)):
    Session = get_session_factory()
    with Session() as db:
        rows = db.scalars(select(QualityRuleRecord).where(
            QualityRuleRecord.workspace_id == user["workspace"]["id"]
        ).order_by(QualityRuleRecord.updated_at.desc())).all()
        return [_serialize(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_rule(payload: RuleDefinition, user: dict = Depends(require_roles("owner", "admin", "analyst"))):
    _validate_rule(payload)
    now = datetime.now(timezone.utc)
    row = QualityRuleRecord(
        workspace_id=user["workspace"]["id"], name=payload.name.strip(), description=payload.description,
        rule_type=payload.rule_type, scope=payload.scope, column_name=payload.column_name,
        category=payload.category, severity=payload.severity,
        parameters_json=json.dumps(payload.parameters), recommendation=payload.recommendation,
        is_active=1 if payload.is_active else 0, created_by_user_id=user["id"], created_at=now, updated_at=now,
    )
    Session = get_session_factory()
    with Session() as db:
        db.add(row); db.commit(); db.refresh(row)
        return _serialize(row)


@router.get("/dashboard")
def rules_dashboard(user: dict = Depends(require_user)):
    workspace_id = user["workspace"]["id"]
    Session = get_session_factory()
    with Session() as db:
        rules = db.scalars(select(QualityRuleRecord).where(QualityRuleRecord.workspace_id == workspace_id).order_by(QualityRuleRecord.updated_at.desc())).all()
        dataset_ids = db.scalars(select(DatasetRecord.id).where(DatasetRecord.workspace_id == workspace_id)).all()
        assignments = db.execute(select(DatasetRuleAssignmentRecord.rule_id, DatasetRuleAssignmentRecord.dataset_id).join(QualityRuleRecord, QualityRuleRecord.id == DatasetRuleAssignmentRecord.rule_id).where(QualityRuleRecord.workspace_id == workspace_id, DatasetRuleAssignmentRecord.is_active == 1)).all()
        executions = db.execute(select(RuleExecutionRecord, QualityRuleRecord.name).join(QualityRuleRecord, QualityRuleRecord.id == RuleExecutionRecord.rule_id).where(QualityRuleRecord.workspace_id == workspace_id).order_by(RuleExecutionRecord.executed_at.desc())).all()
        assignment_counts = {}
        for rule_id, dataset_id in assignments:
            assignment_counts[rule_id] = assignment_counts.get(rule_id, 0) + 1
        last_exec = {}
        for execution, name in executions:
            last_exec.setdefault(execution.rule_id, execution.executed_at)
        rule_items = []
        for row in rules:
            item = _serialize(row)
            item["assignment_count"] = assignment_counts.get(row.id, 0)
            item["last_executed_at"] = last_exec.get(row.id)
            rule_items.append(item)
        failures = sum(1 for execution, _ in executions if execution.outcome == "failed")
        return {
            "rules": rule_items,
            "metrics": {
                "total_rules": len(rules),
                "active_rules": sum(1 for row in rules if row.is_active),
                "assigned_datasets": len(set(dataset_id for _, dataset_id in assignments)),
                "contracted_datasets": len(set(db.scalars(select(DataContractRecord.dataset_id).where(DataContractRecord.workspace_id == workspace_id, DataContractRecord.status != "archived")).all())),
                "executions": len(executions),
                "failing": failures,
                "failure_rate": round((failures / len(executions) * 100), 1) if executions else 0,
            },
            "recent_executions": [{
                "rule_id": execution.rule_id, "rule_name": name, "audit_id": execution.audit_id,
                "outcome": execution.outcome, "affected_rows": execution.affected_rows,
                "affected_rate": execution.affected_rate, "message": execution.message,
                "executed_at": execution.executed_at,
            } for execution, name in executions[:30]],
            "assignments": [{"rule_id": rule_id, "dataset_id": dataset_id} for rule_id, dataset_id in assignments],
        }


@router.get("/contracts")
def list_contracts(user: dict = Depends(require_user)):
    wid = user["workspace"]["id"]
    Session = get_session_factory()
    with Session() as db:
        rows = db.execute(
            select(DataContractRecord, DatasetRecord.name)
            .join(DatasetRecord, DatasetRecord.id == DataContractRecord.dataset_id)
            .where(DataContractRecord.workspace_id == wid)
            .order_by(DataContractRecord.dataset_id, DataContractRecord.version.desc(), DataContractRecord.id.desc())
        ).all()
        latest = {}
        for row, dataset_name in rows:
            latest.setdefault(row.dataset_id, _serialize_contract(row, dataset_name))
        return list(latest.values())


@router.post("/contracts", status_code=201)
def create_contract(payload: ContractPayload, user: dict = Depends(require_roles("owner", "admin", "analyst"))):
    wid = user["workspace"]["id"]
    now = datetime.now(timezone.utc)
    Session = get_session_factory()
    with Session() as db:
        dataset = db.scalar(select(DatasetRecord).where(DatasetRecord.id == payload.dataset_id, DatasetRecord.workspace_id == wid))
        if dataset is None:
            raise HTTPException(404, "Dataset not found.")
        existing = db.scalar(select(DataContractRecord).where(
            DataContractRecord.workspace_id == wid,
            DataContractRecord.dataset_id == dataset.id,
        ).order_by(DataContractRecord.version.desc(), DataContractRecord.id.desc()))
        row = DataContractRecord(
            contract_key=existing.contract_key if existing else uuid.uuid4().hex, workspace_id=wid, dataset_id=dataset.id,
            name=payload.name.strip(), description=payload.description, status=payload.status,
            version=(existing.version + 1) if existing else 1, contract_json=json.dumps(payload.contract), source_audit_id=dataset.latest_audit_id,
            validation_status="not_validated", validation_json="{}",
            published_at=now if payload.status == "published" else None,
            created_by_user_id=user["id"], created_at=now, updated_at=now,
        )
        db.add(row); db.commit(); db.refresh(row)
        return _serialize_contract(row, dataset.name)


@router.post("/contracts/generate/{dataset_id}", status_code=201)
def generate_dataset_contract(dataset_id: int, user: dict = Depends(require_roles("owner", "admin", "analyst"))):
    wid = user["workspace"]["id"]
    now = datetime.now(timezone.utc)
    Session = get_session_factory()
    with Session() as db:
        dataset = db.scalar(select(DatasetRecord).where(DatasetRecord.id == dataset_id, DatasetRecord.workspace_id == wid))
        if dataset is None:
            raise HTTPException(404, "Dataset not found.")
        if not dataset.latest_audit_id:
            raise HTTPException(409, "Run an audit before generating a contract.")
        audit_row = db.scalar(select(AuditRecord).where(AuditRecord.audit_id == dataset.latest_audit_id, AuditRecord.workspace_id == wid))
        if audit_row is None:
            raise HTTPException(404, "Latest audit not found.")
        audit = AuditResult.model_validate(json.loads(audit_row.payload_json))
        assigned_rules = assigned_rules_for_dataset(wid, dataset.name)
        contract = generate_contract(audit, assigned_rules).model_dump(mode="json")
        existing = db.scalar(select(DataContractRecord).where(
            DataContractRecord.workspace_id == wid,
            DataContractRecord.dataset_id == dataset.id,
        ).order_by(DataContractRecord.version.desc(), DataContractRecord.id.desc()))
        row = DataContractRecord(
            contract_key=existing.contract_key if existing else uuid.uuid4().hex, workspace_id=wid, dataset_id=dataset.id,
            name=f"{dataset.name} reliability contract", description="Generated from the latest completed audit.",
            status="draft", version=(existing.version + 1) if existing else 1, contract_json=json.dumps(contract), source_audit_id=dataset.latest_audit_id,
            validation_status="not_validated", validation_json="{}", created_by_user_id=user["id"],
            created_at=now, updated_at=now,
        )
        db.add(row); db.commit(); db.refresh(row)
        return _serialize_contract(row, dataset.name)


@router.get("/contracts/{contract_id}")
def get_contract_record(contract_id: int, user: dict = Depends(require_user)):
    wid = user["workspace"]["id"]
    Session = get_session_factory()
    with Session() as db:
        result = db.execute(select(DataContractRecord, DatasetRecord.name).join(DatasetRecord).where(DataContractRecord.id == contract_id, DataContractRecord.workspace_id == wid)).first()
        if result is None:
            raise HTTPException(404, "Data contract not found.")
        return _serialize_contract(result[0], result[1])


@router.patch("/contracts/{contract_id}", status_code=201)
def update_contract_record(contract_id: int, payload: ContractPayload, user: dict = Depends(require_roles("owner", "admin", "analyst"))):
    wid = user["workspace"]["id"]
    now = datetime.now(timezone.utc)
    Session = get_session_factory()
    with Session() as db:
        current = db.scalar(select(DataContractRecord).where(DataContractRecord.id == contract_id, DataContractRecord.workspace_id == wid))
        dataset = db.scalar(select(DatasetRecord).where(DatasetRecord.id == payload.dataset_id, DatasetRecord.workspace_id == wid))
        if current is None or dataset is None:
            raise HTTPException(404, "Data contract or dataset not found.")
        row = DataContractRecord(
            contract_key=current.contract_key, workspace_id=wid, dataset_id=dataset.id,
            name=payload.name.strip(), description=payload.description, status=payload.status,
            version=current.version + 1, contract_json=json.dumps(payload.contract), source_audit_id=dataset.latest_audit_id,
            validation_status="not_validated", validation_json="{}",
            published_at=now if payload.status == "published" else None,
            created_by_user_id=user["id"], created_at=now, updated_at=now,
        )
        db.add(row); db.commit(); db.refresh(row)
        return _serialize_contract(row, dataset.name)


@router.get("/contracts/{contract_id}/versions")
def contract_versions(contract_id: int, user: dict = Depends(require_user)):
    wid = user["workspace"]["id"]
    Session = get_session_factory()
    with Session() as db:
        current = db.scalar(select(DataContractRecord).where(DataContractRecord.id == contract_id, DataContractRecord.workspace_id == wid))
        if current is None:
            raise HTTPException(404, "Data contract not found.")
        rows = db.execute(select(DataContractRecord, DatasetRecord.name).join(DatasetRecord).where(DataContractRecord.workspace_id == wid, DataContractRecord.contract_key == current.contract_key).order_by(DataContractRecord.version.desc())).all()
        return [_serialize_contract(row, dataset_name) for row, dataset_name in rows]


def _latest_audit_for_latest_dataset_version(db, workspace_id: int, dataset_name: str) -> tuple[AuditRecord, AuditResult] | None:
    rows = db.scalars(
        select(AuditRecord)
        .where(AuditRecord.workspace_id == workspace_id, AuditRecord.dataset_name == dataset_name)
        .order_by(AuditRecord.created_at.desc())
    ).all()
    parsed: list[tuple[AuditRecord, AuditResult]] = []
    for audit_row in rows:
        try:
            parsed.append((audit_row, AuditResult.model_validate(json.loads(audit_row.payload_json))))
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
    if not parsed:
        return None
    versioned = [item for item in parsed if item[1].dataset_version is not None]
    if not versioned:
        return parsed[0]
    latest_version = max(int(item[1].dataset_version or 0) for item in versioned)
    return next(item for item in versioned if int(item[1].dataset_version or 0) == latest_version)


def _schema_contract_violations(contract: dict, audit: AuditResult) -> list[dict]:
    columns = {column.name: column.inferred_type for column in audit.profile.columns}
    violations: list[dict] = []
    for column in contract.get("required_columns", []):
        if column not in columns:
            violations.append({
                "kind": "required_column", "column": column, "expected": "column present",
                "observed": "missing", "affected_rows": audit.profile.row_count,
                "message": f"Required column '{column}' is missing.",
            })
    for column, expected in contract.get("expected_types", {}).items():
        actual = columns.get(column)
        if actual is not None and actual != expected:
            violations.append({
                "kind": "expected_type", "column": column, "expected": expected,
                "observed": actual, "affected_rows": audit.profile.row_count,
                "message": f"Column '{column}' is {actual}; expected {expected}.",
            })
    return violations


def _rule_contract_violations(contract: dict, audit: AuditResult) -> list[dict]:
    sources = contract.get("assigned_rule_sources", []) or []
    expected_rule_ids = {int(source["rule_id"]) for source in sources if source.get("rule_id") is not None}
    executions = {int(item.rule_id): item for item in audit.rule_executions if item.rule_id is not None}
    source_by_id = {int(source["rule_id"]): source for source in sources if source.get("rule_id") is not None}
    violations: list[dict] = []
    for rule_id in sorted(expected_rule_ids):
        source = source_by_id[rule_id]
        execution = executions.get(rule_id)
        if execution is None:
            violations.append({
                "kind": "rule_not_executed", "rule_id": rule_id, "rule_name": source.get("name"),
                "column": source.get("column"), "expected": source.get("rule_type"),
                "observed": "not executed", "affected_rows": 0,
                "message": f"Assigned rule '{source.get('name')}' was not executed for this audit.",
            })
            continue
        if execution.outcome in {"failed", "warning"}:
            column = source.get("column")
            rule_type = execution.rule_type
            expected: object = source.get("rule_type")
            if rule_type == "email":
                expected = "valid email format"
            elif rule_type == "allowed_values":
                expected = contract.get("allowed_values", {}).get(column, "configured allowed values")
            elif rule_type == "numeric_range":
                bounds = contract.get("numeric_ranges", {}).get(column, {}) or {}
                minimum, maximum = bounds.get("min"), bounds.get("max")
                if minimum is not None and maximum is not None:
                    expected = f"{minimum} to {maximum}"
                elif minimum is not None:
                    expected = f">= {minimum}"
                elif maximum is not None:
                    expected = f"<= {maximum}"
            elif rule_type == "required":
                expected = "value present"
            elif rule_type == "unique":
                expected = "unique values"
            observed = f"{execution.affected_rows} affected row(s)"
            violations.append({
                "kind": "assigned_rule", "rule_id": rule_id, "rule_name": execution.rule_name,
                "rule_type": rule_type, "column": column,
                "expected": expected, "observed": observed,
                "affected_rows": execution.affected_rows, "affected_rate": execution.affected_rate,
                "message": execution.message,
            })
    return violations


@router.post("/contracts/{contract_id}/validate")
def validate_contract_record(contract_id: int, user: dict = Depends(require_user)):
    wid = user["workspace"]["id"]
    now = datetime.now(timezone.utc)
    Session = get_session_factory()
    with Session() as db:
        row = db.scalar(select(DataContractRecord).where(DataContractRecord.id == contract_id, DataContractRecord.workspace_id == wid))
        if row is None:
            raise HTTPException(404, "Data contract not found.")
        dataset = db.scalar(select(DatasetRecord).where(DatasetRecord.id == row.dataset_id, DatasetRecord.workspace_id == wid))
        if dataset is None:
            raise HTTPException(404, "Dataset not found.")
        latest = _latest_audit_for_latest_dataset_version(db, wid, dataset.name)
        if latest is None:
            raise HTTPException(409, "A completed audit is required for validation.")
        audit_row, audit = latest
        contract = json.loads(row.contract_json or "{}")
        violation_details = _schema_contract_violations(contract, audit) + _rule_contract_violations(contract, audit)
        dataset_version = audit.dataset_version
        if dataset_version is None:
            dataset_audits = db.scalars(
                select(AuditRecord)
                .where(AuditRecord.workspace_id == wid, AuditRecord.dataset_name == dataset.name)
                .order_by(AuditRecord.created_at)
            ).all()
            lineage = lineage_audits(dataset_audits)
            dataset_version = next((index for index, item in enumerate(lineage, 1) if item.audit_id == audit_row.audit_id), None)
            if dataset_version is None:
                dataset_version = len(lineage) or 1
        result = {
            "passed": not violation_details,
            "violation_count": len(violation_details),
            "violations": violation_details,
            "missing_columns": [item["column"] for item in violation_details if item["kind"] == "required_column"],
            "type_mismatches": [item for item in violation_details if item["kind"] == "expected_type"],
            "audit_id": audit.audit_id,
            "dataset_version": dataset_version,
            "audit_kind": audit.audit_kind,
            "validated_at": now.isoformat(),
        }
        row.source_audit_id = audit.audit_id
        row.validation_status = "passed" if result["passed"] else "failed"
        row.validation_json = json.dumps(result)
        row.validated_at = now
        row.updated_at = now
        db.commit()
        db.refresh(row)
        return _serialize_contract(row, dataset.name)


@router.post("/contracts/{contract_id}/status", status_code=201)
def transition_contract_status(contract_id: int, payload: ContractStatusPayload, user: dict = Depends(require_roles("owner", "admin", "analyst"))):
    wid = user["workspace"]["id"]
    now = datetime.now(timezone.utc)
    Session = get_session_factory()
    with Session() as db:
        current = db.scalar(select(DataContractRecord).where(DataContractRecord.id == contract_id, DataContractRecord.workspace_id == wid))
        if current is None:
            raise HTTPException(404, "Data contract not found.")
        dataset = db.scalar(select(DatasetRecord).where(DatasetRecord.id == current.dataset_id, DatasetRecord.workspace_id == wid))
        row = DataContractRecord(
            contract_key=current.contract_key, workspace_id=wid, dataset_id=current.dataset_id,
            name=current.name, description=current.description, status=payload.status,
            version=current.version + 1, contract_json=current.contract_json, source_audit_id=current.source_audit_id,
            validation_status=current.validation_status, validation_json=current.validation_json,
            validated_at=current.validated_at, published_at=now if payload.status == "published" else current.published_at,
            created_by_user_id=user["id"], created_at=now, updated_at=now,
        )
        db.add(row); db.commit(); db.refresh(row)
        return _serialize_contract(row, dataset.name if dataset else None)


@router.post("/assignments/bulk")
def bulk_assignments(payload: BulkAssignmentPayload, user: dict = Depends(require_roles("owner", "admin", "analyst"))):
    wid = user["workspace"]["id"]
    Session = get_session_factory()
    changed = 0
    with Session() as db:
        rules = db.scalars(select(QualityRuleRecord).where(QualityRuleRecord.workspace_id == wid, QualityRuleRecord.id.in_(payload.rule_ids))).all()
        datasets = db.scalars(select(DatasetRecord).where(DatasetRecord.workspace_id == wid, DatasetRecord.id.in_(payload.dataset_ids))).all()
        if len(rules) != len(set(payload.rule_ids)) or len(datasets) != len(set(payload.dataset_ids)):
            raise HTTPException(404, "One or more rules or datasets were not found.")
        for rule_id in payload.rule_ids:
            for dataset_id in payload.dataset_ids:
                existing = db.scalar(select(DatasetRuleAssignmentRecord).where(DatasetRuleAssignmentRecord.rule_id == rule_id, DatasetRuleAssignmentRecord.dataset_id == dataset_id))
                desired = 1 if payload.action == "assign" else 0
                if existing:
                    if existing.is_active != desired:
                        existing.is_active = desired; changed += 1
                elif desired:
                    db.add(DatasetRuleAssignmentRecord(rule_id=rule_id, dataset_id=dataset_id, is_active=1, created_at=datetime.now(timezone.utc))); changed += 1
        db.commit()
    return {"changed": changed, "action": payload.action}


@router.get("/executions")
def execution_history(
    outcome: str = Query(default="all"), rule_id: int | None = None, dataset_id: int | None = None,
    search: str = Query(default=""), page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=200),
    user: dict = Depends(require_user),
):
    wid = user["workspace"]["id"]
    Session = get_session_factory()
    with Session() as db:
        stmt = select(RuleExecutionRecord, QualityRuleRecord.name, AuditRecord.dataset_name).join(QualityRuleRecord, QualityRuleRecord.id == RuleExecutionRecord.rule_id).join(AuditRecord, AuditRecord.audit_id == RuleExecutionRecord.audit_id).where(QualityRuleRecord.workspace_id == wid, AuditRecord.workspace_id == wid)
        if outcome != "all": stmt = stmt.where(RuleExecutionRecord.outcome == outcome)
        if rule_id: stmt = stmt.where(QualityRuleRecord.id == rule_id)
        if dataset_id:
            dataset = db.scalar(select(DatasetRecord).where(DatasetRecord.id == dataset_id, DatasetRecord.workspace_id == wid))
            if dataset is None: raise HTTPException(404, "Dataset not found.")
            stmt = stmt.where(AuditRecord.dataset_name == dataset.name)
        if search.strip(): stmt = stmt.where(func.lower(QualityRuleRecord.name).contains(search.strip().lower()))
        rows = db.execute(stmt.order_by(RuleExecutionRecord.executed_at.desc())).all()
        total = len(rows); start = (page - 1) * page_size
        items = rows[start:start + page_size]
        return {"total": total, "page": page, "page_size": page_size, "items": [{"id": execution.id, "rule_id": execution.rule_id, "rule_name": rule_name, "dataset_name": dataset_name, "audit_id": execution.audit_id, "outcome": execution.outcome, "affected_rows": execution.affected_rows, "affected_rate": execution.affected_rate, "affected_percentage": round(execution.affected_rate * 100, 2), "message": execution.message, "executed_at": execution.executed_at} for execution, rule_name, dataset_name in items]}


@router.get("/executions/export.csv")
def export_execution_history(user: dict = Depends(require_user)):
    data = execution_history(outcome="all", rule_id=None, dataset_id=None, search="", page=1, page_size=200, user=user)
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(["Rule", "Dataset", "Outcome", "Affected rows", "Affected percentage", "Executed", "Audit"])
    for item in data["items"]:
        writer.writerow([item["rule_name"], item["dataset_name"], item["outcome"], item["affected_rows"], item["affected_percentage"], item["executed_at"], item["audit_id"]])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=rule_execution_history.csv"})


class RuleBuilderTestPayload(BaseModel):
    dataset_id: int
    rule: RuleDefinition


@router.get("/builder/context/{dataset_id}")
def rule_builder_context(dataset_id: int, user: dict = Depends(require_user)):
    """Return dataset columns and profile metadata for guided rule creation."""
    wid = user["workspace"]["id"]
    Session = get_session_factory()
    with Session() as db:
        dataset = db.scalar(select(DatasetRecord).where(DatasetRecord.id == dataset_id, DatasetRecord.workspace_id == wid))
        if dataset is None:
            raise HTTPException(404, "Dataset not found.")
        columns = []
        if dataset.latest_audit_id:
            audit = db.scalar(select(AuditRecord).where(AuditRecord.audit_id == dataset.latest_audit_id, AuditRecord.workspace_id == wid))
            if audit:
                payload = json.loads(audit.payload_json)
                columns = [{
                    "name": col.get("name"),
                    "inferred_type": col.get("inferred_type", "text"),
                    "missing_rate": col.get("missing_rate", 0),
                    "unique_rate": col.get("unique_rate", 0),
                } for col in payload.get("profile", {}).get("columns", [])]
        return {"dataset": {"id": dataset.id, "name": dataset.name, "record_count": dataset.record_count}, "columns": columns}


@router.post("/builder/test")
def test_rule_builder(payload: RuleBuilderTestPayload, user: dict = Depends(require_roles("owner", "admin", "analyst"))):
    """Execute an unsaved rule against a dataset and return a safe impact preview."""
    _validate_rule(payload.rule)
    wid = user["workspace"]["id"]
    Session = get_session_factory()
    with Session() as db:
        dataset = db.scalar(select(DatasetRecord).where(DatasetRecord.id == payload.dataset_id, DatasetRecord.workspace_id == wid))
        if dataset is None:
            raise HTTPException(404, "Dataset not found.")
        if not dataset.latest_audit_id:
            raise HTTPException(409, "Import and audit the dataset before testing a rule.")
        upload = db.scalar(select(UploadRecord).where(UploadRecord.audit_id == dataset.latest_audit_id))
        path = get_settings().root_dir / upload.relative_path if upload is not None else get_settings().root_dir / "samples" / "customers_dirty.csv"
        if not path.exists():
            raise HTTPException(409, "The source file for the latest audit is unavailable.")
    frame = read_csv_path(path)
    issues, executions = execute_quality_rules(frame, [payload.rule])
    execution = executions[0]
    issue = issues[0] if issues else None
    return {
        "outcome": execution.outcome,
        "affected_rows": execution.affected_rows,
        "affected_percentage": round(execution.affected_rate * 100, 2),
        "total_rows": len(frame),
        "message": execution.message,
        "examples": issue.examples[:5] if issue else [],
        "estimated_score_impact": min(25, round(execution.affected_rate * 100 * {"critical": 1.0, "high": .75, "medium": .45, "low": .2}.get(payload.rule.severity, .45), 1)),
    }


@router.get("/{rule_id}")
def get_rule(rule_id: int, user: dict = Depends(require_user)):
    return _get_rule(rule_id, user["workspace"]["id"])


@router.patch("/{rule_id}")
def update_rule(rule_id: int, payload: RuleDefinition, user: dict = Depends(require_roles("owner", "admin", "analyst"))):
    _validate_rule(payload)
    Session = get_session_factory()
    with Session() as db:
        row = db.scalar(select(QualityRuleRecord).where(
            QualityRuleRecord.id == rule_id,
            QualityRuleRecord.workspace_id == user["workspace"]["id"],
        ))
        if row is None: raise HTTPException(404, "Quality rule not found.")
        for field in ("name", "description", "rule_type", "scope", "column_name", "category", "severity", "recommendation"):
            setattr(row, field, getattr(payload, field))
        row.parameters_json = json.dumps(payload.parameters)
        row.is_active = 1 if payload.is_active else 0
        row.updated_at = datetime.now(timezone.utc)
        db.commit(); db.refresh(row)
        return _serialize(row)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, user: dict = Depends(require_roles("owner", "admin"))):
    Session = get_session_factory()
    with Session() as db:
        row = db.scalar(select(QualityRuleRecord).where(
            QualityRuleRecord.id == rule_id,
            QualityRuleRecord.workspace_id == user["workspace"]["id"],
        ))
        if row is None: raise HTTPException(404, "Quality rule not found.")
        db.delete(row); db.commit()


@router.post("/{rule_id}/assign/{dataset_id}", status_code=201)
def assign_rule(rule_id: int, dataset_id: int, user: dict = Depends(require_roles("owner", "admin", "analyst"))):
    workspace_id = user["workspace"]["id"]
    Session = get_session_factory()
    with Session() as db:
        rule = db.scalar(select(QualityRuleRecord).where(QualityRuleRecord.id == rule_id, QualityRuleRecord.workspace_id == workspace_id))
        dataset = db.scalar(select(DatasetRecord).where(DatasetRecord.id == dataset_id, DatasetRecord.workspace_id == workspace_id))
        if rule is None or dataset is None: raise HTTPException(404, "Rule or dataset not found.")
        existing = db.scalar(select(DatasetRuleAssignmentRecord).where(
            DatasetRuleAssignmentRecord.rule_id == rule_id,
            DatasetRuleAssignmentRecord.dataset_id == dataset_id,
        ))
        if existing:
            existing.is_active = 1
        else:
            db.add(DatasetRuleAssignmentRecord(rule_id=rule_id, dataset_id=dataset_id, is_active=1, created_at=datetime.now(timezone.utc)))
        db.commit()
        return {"rule_id": rule_id, "dataset_id": dataset_id, "assigned": True}


@router.delete("/{rule_id}/assign/{dataset_id}", status_code=204)
def unassign_rule(rule_id: int, dataset_id: int, user: dict = Depends(require_roles("owner", "admin", "analyst"))):
    workspace_id = user["workspace"]["id"]
    Session = get_session_factory()
    with Session() as db:
        dataset = db.scalar(select(DatasetRecord).where(DatasetRecord.id == dataset_id, DatasetRecord.workspace_id == workspace_id))
        rule = db.scalar(select(QualityRuleRecord).where(QualityRuleRecord.id == rule_id, QualityRuleRecord.workspace_id == workspace_id))
        if dataset is None or rule is None: raise HTTPException(404, "Rule or dataset not found.")
        db.execute(delete(DatasetRuleAssignmentRecord).where(
            DatasetRuleAssignmentRecord.rule_id == rule_id,
            DatasetRuleAssignmentRecord.dataset_id == dataset_id,
        )); db.commit()


@router.get("/{rule_id}/executions")
def rule_execution_history(rule_id: int, user: dict = Depends(require_user)):
    _get_rule(rule_id, user["workspace"]["id"])
    Session = get_session_factory()
    with Session() as db:
        rows = db.scalars(select(RuleExecutionRecord).where(RuleExecutionRecord.rule_id == rule_id).order_by(RuleExecutionRecord.executed_at.desc())).all()
        return [{"audit_id": row.audit_id, "outcome": row.outcome, "affected_rows": row.affected_rows,
                 "affected_rate": row.affected_rate, "message": row.message, "executed_at": row.executed_at} for row in rows]


def _get_rule(rule_id: int, workspace_id: int):
    Session = get_session_factory()
    with Session() as db:
        row = db.scalar(select(QualityRuleRecord).where(QualityRuleRecord.id == rule_id, QualityRuleRecord.workspace_id == workspace_id))
        if row is None: raise HTTPException(404, "Quality rule not found.")
        return _serialize(row)


def _validate_rule(payload: RuleDefinition) -> None:
    if payload.scope == "column" and not payload.column_name:
        raise HTTPException(422, "Column rules require column_name.")
    if payload.scope == "dataset" and payload.rule_type != "duplicate_rows":
        raise HTTPException(422, "Only duplicate_rows is currently supported for dataset-level rules.")
    required = {
        "allowed_values": "values", "regex": "pattern", "numeric_range": None,
        "length_range": None, "missing_threshold": "max_rate", "expected_type": "type", "stale_days": "days",
    }
    key = required.get(payload.rule_type)
    if key and key not in payload.parameters:
        raise HTTPException(422, f"{payload.rule_type} rules require the '{key}' parameter.")

