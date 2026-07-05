from __future__ import annotations

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
            description="Mask, hash, or remove sensitive fields before sharing data or sending context to an LLM.",
            pandas_code="\n".join(f"{frame_ref}[{column!r}] = '***MASKED***'" for column in issue.columns),
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
