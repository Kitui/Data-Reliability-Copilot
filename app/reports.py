from __future__ import annotations

from app.schemas import AuditResult


def build_markdown_report(audit: AuditResult) -> str:
    lines = [
        f"# Data Quality Audit: {audit.dataset_name}",
        "",
        f"- Audit ID: `{audit.audit_id}`",
        f"- Created: `{audit.created_at.isoformat()}`",
        f"- Overall score: **{audit.score.overall}/100**",
        f"- Risk level: **{audit.summary.risk_level}**",
        f"- Summary source: `{audit.summary.source}`",
        "",
        "## Executive Summary",
        "",
        audit.summary.executive_summary,
        "",
        "## Score Breakdown",
        "",
        "| Dimension | Score |",
        "| --- | ---: |",
        f"| Completeness | {audit.score.completeness} |",
        f"| Validity | {audit.score.validity} |",
        f"| Consistency | {audit.score.consistency} |",
        f"| Uniqueness | {audit.score.uniqueness} |",
        f"| Reliability | {audit.score.reliability} |",
        "",
        "## Recommended Focus",
        "",
    ]
    lines.extend(f"- {item}" for item in audit.summary.recommended_focus)
    lines.extend(["", "## Remediation Plan", ""])
    lines.extend(f"- {item}" for item in audit.summary.remediation_plan)
    lines.extend(["", "## Issues", ""])

    if not audit.issues:
        lines.append("No issues were detected by the configured rules.")
    else:
        lines.extend(
            [
                "| ID | Severity | Category | Affected Rows | Columns | Finding | Recommendation |",
                "| --- | --- | --- | ---: | --- | --- | --- |",
            ]
        )
        for issue in audit.issues:
            lines.append(
                "| "
                + " | ".join(
                    [
                        issue.id,
                        issue.severity,
                        issue.category,
                        str(issue.affected_rows),
                        ", ".join(issue.columns),
                        _escape_table(issue.title),
                        _escape_table(issue.recommendation),
                    ]
                )
                + " |"
            )

    lines.extend(["", "## Column Profile", ""])
    lines.extend(
        [
            "| Column | Type | Missing | Unique Values |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for column in audit.profile.columns:
        lines.append(
            f"| {column.name} | {column.inferred_type} | {column.missing_rate:.0%} | {column.unique_count} |"
        )

    return "\n".join(lines) + "\n"


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
