from __future__ import annotations

import json
from collections.abc import Sequence

from app.db.models import AuditRecord


def _metadata(audit: AuditRecord) -> tuple[str | None, int | None]:
    try:
        payload = json.loads(audit.payload_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return None, None
    kind = payload.get("audit_kind")
    version = payload.get("dataset_version")
    try:
        version = int(version) if version is not None else None
    except (TypeError, ValueError):
        version = None
    return kind, version


def lineage_audits(audits: Sequence[AuditRecord]) -> list[AuditRecord]:
    """Return immutable source revisions while excluding audit executions.

    New records carry explicit audit kind/version metadata. Legacy databases are
    reconstructed from source-filename transitions, because reruns retained the
    same source filename while version imports introduced a new one.
    """
    ordered = sorted(audits, key=lambda row: (row.created_at, row.audit_id))
    versions: dict[int, AuditRecord] = {}
    last_source: str | None = None

    for audit in ordered:
        kind, version = _metadata(audit)
        source = audit.upload.original_filename if audit.upload else None

        if kind in {"dataset_import", "version_import"} and version:
            versions.setdefault(version, audit)
            last_source = source or last_source
            continue
        if kind in {"rerun", "scheduled", "sample", "remediation"}:
            continue

        # Legacy records did not carry audit-kind metadata.
        if not versions:
            versions[1] = audit
            last_source = source
        elif source and source != last_source:
            number = max(versions) + 1
            versions[number] = audit
            last_source = source

    return [versions[number] for number in sorted(versions)]


def current_dataset_version(audits: Sequence[AuditRecord]) -> int:
    return max(1, len(lineage_audits(audits))) if audits else 1
