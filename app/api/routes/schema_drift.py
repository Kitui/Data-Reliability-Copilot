from __future__ import annotations

import csv
import io
import json
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.auth_dependencies import require_user
from app.db.models import AuditRecord, DatasetRecord
from app.db.session import get_session_factory
from app.versioning import lineage_audits

router = APIRouter(prefix="/schema-drift", tags=["Schema Drift"])


def _profile(row: AuditRecord) -> dict:
    try:
        return json.loads(row.payload_json or "{}").get("profile", {})
    except (TypeError, json.JSONDecodeError):
        return {}


def _columns(row: AuditRecord) -> dict[str, dict]:
    return {str(item.get("name")): item for item in _profile(row).get("columns", []) if item.get("name")}


def _severity(impact: int) -> str:
    return "high" if impact >= 70 else "medium" if impact >= 35 else "low"


def _event(
    dataset: DatasetRecord,
    before: AuditRecord,
    after: AuditRecord,
    drift_type: str,
    key: str,
    description: str,
    affected: list[dict],
    impact: int,
    version_from: int,
    version_to: int,
) -> dict:
    return {
        "id": f"{dataset.id}:{after.audit_id}:{drift_type}:{key}",
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "baseline_audit_id": before.audit_id,
        "candidate_audit_id": after.audit_id,
        "baseline_version": version_from,
        "candidate_version": version_to,
        "drift_type": drift_type,
        "severity": _severity(impact),
        "impact_score": min(100, max(1, impact)),
        "description": description,
        "affected_columns": affected,
        "detected_at": after.created_at,
        "signature": f"{dataset.id}:{drift_type}:{key}",
        "contract_aware": False,
        "status": "new",
    }


def _pair_events(
    dataset: DatasetRecord, before: AuditRecord, after: AuditRecord, version_from: int, version_to: int
) -> list[dict]:
    old, new = _columns(before), _columns(after)
    events: list[dict] = []
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    if added:
        impact = min(96, 40 + 14 * len(added))
        events.append(
            _event(
                dataset,
                before,
                after,
                "column_added",
                ",".join(added),
                f"{len(added)} column{'s were' if len(added) != 1 else ' was'} added in version v{version_to}.",
                [{"name": c, "before": None, "after": new[c].get("inferred_type", "unknown")} for c in added],
                impact,
                version_from,
                version_to,
            )
        )
    if removed:
        impact = min(100, 55 + 15 * len(removed))
        events.append(
            _event(
                dataset,
                before,
                after,
                "column_removed",
                ",".join(removed),
                f"{len(removed)} column{'s were' if len(removed) != 1 else ' was'} removed in version v{version_to}.",
                [{"name": c, "before": old[c].get("inferred_type", "unknown"), "after": None} for c in removed],
                impact,
                version_from,
                version_to,
            )
        )
    for name in sorted(set(old) & set(new)):
        old_type, new_type = old[name].get("inferred_type"), new[name].get("inferred_type")
        if old_type != new_type:
            events.append(
                _event(
                    dataset,
                    before,
                    after,
                    "type_changed",
                    name,
                    f"Column {name} changed type from {old_type or 'unknown'} to {new_type or 'unknown'}.",
                    [{"name": name, "before": old_type, "after": new_type}],
                    78,
                    version_from,
                    version_to,
                )
            )
        old_missing = float(old[name].get("missing_rate") or 0)
        new_missing = float(new[name].get("missing_rate") or 0)
        delta = abs(new_missing - old_missing)
        if delta >= 0.10:
            impact = min(90, int(25 + delta * 100))
            events.append(
                _event(
                    dataset,
                    before,
                    after,
                    "nullability_changed",
                    name,
                    f"Column {name} missing-value rate changed from {old_missing:.1%} to {new_missing:.1%}.",
                    [{"name": name, "before": old_missing, "after": new_missing}],
                    impact,
                    version_from,
                    version_to,
                )
            )
        old_unique = old[name].get("unique_count") or old[name].get("distinct_count")
        new_unique = new[name].get("unique_count") or new[name].get("distinct_count")
        if old_unique and new_unique and old_unique > 0:
            ratio = abs(float(new_unique) - float(old_unique)) / float(old_unique)
            if ratio >= 0.30:
                impact = min(85, int(20 + ratio * 55))
                events.append(
                    _event(
                        dataset,
                        before,
                        after,
                        "cardinality_shift",
                        name,
                        f"Column {name} cardinality shifted from {old_unique} to {new_unique} distinct values.",
                        [{"name": name, "before": old_unique, "after": new_unique}],
                        impact,
                        version_from,
                        version_to,
                    )
                )
    return events


def _all_events(workspace_id: int) -> list[dict]:
    Session = get_session_factory()
    with Session() as db:
        datasets = db.scalars(select(DatasetRecord).where(DatasetRecord.workspace_id == workspace_id)).all()
        results: list[dict] = []
        for dataset in datasets:
            audits = db.scalars(
                select(AuditRecord)
                .where(
                    AuditRecord.workspace_id == workspace_id,
                    AuditRecord.dataset_name == dataset.name,
                )
                .order_by(AuditRecord.created_at.asc())
            ).all()
            audits = lineage_audits(audits)
            dataset_events: list[dict] = []
            for index in range(1, len(audits)):
                dataset_events.extend(_pair_events(dataset, audits[index - 1], audits[index], index, index + 1))
            signatures_by_pair: dict[int, set[str]] = {}
            for item in dataset_events:
                signatures_by_pair.setdefault(item["candidate_version"], set()).add(item["signature"])
            latest_version = len(audits)
            for item in dataset_events:
                if item["candidate_version"] == latest_version:
                    previous = signatures_by_pair.get(latest_version - 1, set())
                    item["status"] = "persistent" if item["signature"] in previous else "new"
                elif item["candidate_version"] < latest_version:
                    later = set().union(
                        *(
                            signatures_by_pair.get(v, set())
                            for v in range(item["candidate_version"] + 1, latest_version + 1)
                        )
                    )
                    item["status"] = "persistent" if item["signature"] in later else "resolved"
            results.extend(dataset_events)
    return sorted(results, key=lambda item: item["detected_at"], reverse=True)


@router.get("")
def list_schema_drift(
    dataset_id: int | None = Query(default=None),
    drift_type: str = Query(default="all"),
    severity: str = Query(default="all"),
    status: str = Query(default="all"),
    search: str = Query(default=""),
    user: dict = Depends(require_user),
):
    events = _all_events(user["workspace"]["id"])
    if dataset_id is not None:
        events = [x for x in events if x["dataset_id"] == dataset_id]
    if drift_type != "all":
        events = [x for x in events if x["drift_type"] == drift_type]
    if severity != "all":
        events = [x for x in events if x["severity"] == severity]
    if status != "all":
        events = [x for x in events if x["status"] == status]
    if search.strip():
        needle = search.strip().lower()
        events = [x for x in events if needle in x["dataset_name"].lower() or needle in x["description"].lower()]
    severities = Counter(x["severity"] for x in events)
    types = Counter(x["drift_type"] for x in events)
    average = round(sum(x["impact_score"] for x in events) / len(events)) if events else 0
    by_day = Counter(x["detected_at"].date().isoformat() for x in events)
    return {
        "summary": {
            "total": len(events),
            "high": severities["high"],
            "medium": severities["medium"],
            "low": severities["low"],
            "average_impact": average,
        },
        "type_counts": dict(types),
        "trend": [{"date": day, "count": by_day[day]} for day in sorted(by_day)],
        "events": events,
    }


@router.get("/export")
def export_schema_drift(user: dict = Depends(require_user)):
    events = _all_events(user["workspace"]["id"])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Dataset",
            "Drift type",
            "Severity",
            "Impact score",
            "Status",
            "Baseline version",
            "Candidate version",
            "Detected",
            "Description",
        ]
    )
    for item in events:
        writer.writerow(
            [
                item["dataset_name"],
                item["drift_type"],
                item["severity"],
                item["impact_score"],
                item["status"],
                item["baseline_version"],
                item["candidate_version"],
                item["detected_at"],
                item["description"],
            ]
        )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=schema_drift_report.csv"},
    )


@router.get("/{event_id:path}")
def get_schema_drift_event(event_id: str, user: dict = Depends(require_user)):
    event = next((x for x in _all_events(user["workspace"]["id"]) if x["id"] == event_id), None)
    if event is None:
        raise HTTPException(404, "Drift event not found in the active workspace.")
    return event
