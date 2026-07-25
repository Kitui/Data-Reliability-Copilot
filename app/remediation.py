from __future__ import annotations

import hashlib
import re

from app.schemas import AuditResult, QualityIssue, RemediationAction, RemediationPlan


def build_remediation_plan(audit: AuditResult) -> RemediationPlan:
    actions = [_action_for_issue(issue) for issue in audit.issues]
    script = _build_script(audit.dataset_name, actions)
    return RemediationPlan(audit_id=audit.audit_id, actions=actions, generated_cleaning_script=script)


def _action_for_issue(issue: QualityIssue) -> RemediationAction:
    column = issue.columns[0] if issue.columns else "column_name"
    frame_ref = "df"
    if issue.category == "uniqueness":
        subset = issue.columns if len(issue.columns) <= 3 else []
        subset_code = f"subset={subset!r}" if subset else ""
        return RemediationAction(
            issue_id=issue.id,
            title=f"Deduplicate records for {issue.title}",
            action_type="deduplicate",
            description="Remove duplicate records after confirming the correct business key.",
            pandas_code=f"{frame_ref} = {frame_ref}.drop_duplicates({subset_code})",
            sql_hint="Use ROW_NUMBER() over the business key and keep the preferred record.",
            risk="medium",
        )
    if issue.category == "completeness":
        return RemediationAction(
            issue_id=issue.id,
            title=f"Handle missing values in {column}",
            action_type="fill_missing",
            description="Review missing values and fill only when a defensible default or source backfill exists.",
            pandas_code=f"{frame_ref}[{column!r}] = {frame_ref}[{column!r}].replace('', None)",
            sql_hint=f"Use NULLIF(TRIM({column}), '') and backfill from a trusted source table.",
            risk="medium",
        )
    if issue.category == "consistency":
        return RemediationAction(
            issue_id=issue.id,
            title=f"Standardize values for {column}",
            action_type="standardize",
            description="Normalize casing and whitespace before grouping, reporting, or model training.",
            pandas_code=f"{frame_ref}[{column!r}] = {frame_ref}[{column!r}].astype(str).str.strip().str.title()",
            sql_hint=f"Use TRIM and a controlled mapping table for {column}.",
            risk="low",
        )
    if issue.category == "privacy":
        return RemediationAction(
            issue_id=issue.id,
            title="Protect sensitive fields",
            action_type="mask",
            description="Pseudonymize sensitive values while preserving valid formats and stable uniqueness wherever possible.",
            pandas_code="\n".join(f"{frame_ref}[{column!r}] = {frame_ref}[{column!r}].map(format_preserving_token)" for column in issue.columns),
            sql_hint="Use hashing, tokenization, or column-level access controls for PII fields.",
            risk="high",
        )
    if issue.category in {"validity", "integrity", "timeliness", "schema"}:
        return RemediationAction(
            issue_id=issue.id,
            title=f"Validate {issue.title}",
            action_type="validate",
            description=issue.recommendation,
            pandas_code=f"# Review rows related to {issue.columns!r} before applying a destructive fix.",
            sql_hint="Add a CHECK constraint, data contract rule, or upstream validation for this condition.",
            risk="high" if issue.severity in {"high", "critical"} else "medium",
        )
    return RemediationAction(
        issue_id=issue.id,
        title=f"Review {issue.title}",
        action_type="review",
        description=issue.recommendation,
        pandas_code=f"# Inspect issue {issue.id}: {issue.title}",
        sql_hint="Review source records and apply a business-approved correction.",
        risk="medium",
    )


def _build_script(dataset_name: str, actions: list[RemediationAction]) -> str:
    lines = [
        "import pandas as pd",
        "",
        f"df = pd.read_csv({dataset_name!r})",
        "",
        "# Generated remediation draft. Review before running on production data.",
    ]
    for action in actions:
        lines.extend(["", f"# {action.issue_id}: {action.title}", action.pandas_code])
    lines.extend(["", "df.to_csv('cleaned_dataset.csv', index=False)"])
    return "\n".join(lines)



def _stable_token(value: object, length: int = 12) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:length]


def _protect_sensitive_value(column: str, value: object) -> object:
    """Return a deterministic pseudonym that preserves common validation formats."""
    import pandas as pd

    if pd.isna(value) or str(value).strip() == "":
        return value
    raw = str(value).strip()
    lowered = column.strip().lower().replace(" ", "_")
    token = _stable_token(raw)

    if "email" in lowered or ("@" in raw and "." in raw.rsplit("@", 1)[-1]):
        return f"user_{token[:10]}@masked.example"
    if any(part in lowered for part in ("phone", "mobile", "telephone")):
        digits = str(int(token[:10], 16)).zfill(10)[-10:]
        return f"+254{digits[-9:]}"
    if any(part in lowered for part in ("name", "customer_name", "full_name")):
        return f"Person {token[:8].upper()}"
    if any(part in lowered for part in ("address", "street")):
        return f"Address {token[:10].upper()}"
    if any(part in lowered for part in ("date_of_birth", "dob")):
        return "1970-01-01"
    if any(part in lowered for part in ("ip_address", "ip")):
        octets = [str((int(token[i:i+2], 16) % 254) + 1) for i in range(0, 8, 2)]
        return ".".join(octets)
    if any(part in lowered for part in ("card", "account", "passport", "national_id", "ssn", "identifier", "customer_id")):
        prefix = re.sub(r"[^A-Za-z]", "", raw)[:2].upper() or "ID"
        return f"{prefix}-{token[:12].upper()}"
    return f"TOKEN-{token.upper()}"

def apply_remediation_actions(frame, audit: AuditResult, issue_ids: list[str], fill_strategy: str = "mode", mask_sensitive: bool = True):
    """Apply conservative, deterministic corrections to a copy of a dataframe."""
    import pandas as pd

    result = frame.copy(deep=True)
    selected = {issue.id: issue for issue in audit.issues if issue.id in set(issue_ids)}
    changed_columns: set[str] = set()
    changed_cells = 0
    removed_rows = 0
    warnings: list[str] = []
    samples: list[dict[str, object]] = []

    def record_change(row, column, before, after):
        nonlocal changed_cells
        changed_cells += 1
        changed_columns.add(column)
        if len(samples) < 20:
            samples.append({"row": int(row) if isinstance(row, int) else str(row), "column": column,
                            "before": None if pd.isna(before) else str(before), "after": None if pd.isna(after) else str(after)})

    for issue in selected.values():
        columns = [c for c in issue.columns if c in result.columns]
        if issue.category == "uniqueness":
            before = len(result)
            subset = columns or None
            result = result.drop_duplicates(subset=subset, keep="first").reset_index(drop=True)
            removed_rows += before - len(result)
        elif issue.category == "completeness":
            for column in columns:
                series = result[column]
                missing = series.isna() | series.astype(str).str.strip().eq("")
                if not missing.any():
                    continue
                if fill_strategy == "zero":
                    replacement = 0
                elif fill_strategy == "blank":
                    replacement = "Not provided"
                else:
                    modes = series[~missing].mode(dropna=True)
                    replacement = modes.iloc[0] if not modes.empty else "Not provided"
                for idx in result.index[missing][:20]:
                    record_change(idx, column, result.at[idx, column], replacement)
                extra = int(missing.sum()) - min(int(missing.sum()), 20)
                if extra > 0:
                    changed_cells += extra
                    changed_columns.add(column)
                result.loc[missing, column] = replacement
        elif issue.category == "consistency":
            for column in columns:
                before_series = result[column].copy()
                after_series = before_series.map(lambda v: v.strip().title() if isinstance(v, str) else v)
                changed = before_series.fillna("<NA>").astype(str) != after_series.fillna("<NA>").astype(str)
                for idx in result.index[changed][:20]:
                    record_change(idx, column, before_series.at[idx], after_series.at[idx])
                extra = int(changed.sum()) - min(int(changed.sum()), 20)
                if extra > 0:
                    changed_cells += extra
                    changed_columns.add(column)
                result[column] = after_series
        elif issue.category == "privacy" and mask_sensitive:
            for column in columns:
                before_series = result[column].copy()
                after_series = before_series.map(lambda value: _protect_sensitive_value(column, value))
                changed = before_series.fillna("<NA>").astype(str) != after_series.fillna("<NA>").astype(str)
                for idx in result.index[changed][:20]:
                    record_change(idx, column, before_series.at[idx], after_series.at[idx])
                extra = int(changed.sum()) - min(int(changed.sum()), 20)
                if extra > 0:
                    changed_cells += extra
                    changed_columns.add(column)
                result[column] = after_series
            warnings.append(f"{issue.title}: applied format-preserving pseudonymization; score impact is determined by the projected audit, not a fixed privacy penalty.")
        else:
            warnings.append(f"{issue.title}: review-only action was not applied automatically.")

    return result, {
        "changed_cells": changed_cells,
        "removed_rows": removed_rows,
        "changed_columns": sorted(changed_columns),
        "sample_changes": samples,
        "warnings": warnings,
    }
