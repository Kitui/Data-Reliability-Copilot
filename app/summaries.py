from __future__ import annotations

from collections import Counter
import json
import os
from typing import Any

from app.schemas import AuditSummary, DatasetProfile, LlmAuditSummary, QualityIssue, QualityScore

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def summarize_audit(profile: DatasetProfile, issues: list[QualityIssue], score: QualityScore) -> AuditSummary:
    context = build_llm_context(profile, issues, score)
    fallback = build_rule_based_summary(profile, issues, score, context)
    llm_summary = generate_llm_summary(context)
    if llm_summary is None:
        return fallback

    return AuditSummary(
        executive_summary=llm_summary.executive_summary,
        recommended_focus=llm_summary.recommended_focus,
        risk_level=llm_summary.risk_level,
        llm_ready_context=context,
        source="llm",
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        confidence=llm_summary.confidence,
        notable_patterns=llm_summary.notable_patterns,
        remediation_plan=llm_summary.remediation_plan,
    )


def build_rule_based_summary(
    profile: DatasetProfile,
    issues: list[QualityIssue],
    score: QualityScore,
    context: dict[str, Any],
) -> AuditSummary:
    severity_counts = Counter(issue.severity for issue in issues)
    top_issues = issues[:3]

    if score.overall < 60 or severity_counts["critical"]:
        risk_level = "critical"
    elif score.overall < 75 or severity_counts["high"]:
        risk_level = "high"
    elif score.overall < 90 or severity_counts["medium"]:
        risk_level = "medium"
    else:
        risk_level = "low"

    if issues:
        issue_phrase = "; ".join(f"{issue.title} affecting {issue.affected_rows} rows" for issue in top_issues)
        executive_summary = (
            f"The dataset contains {profile.row_count} rows and {profile.column_count} columns with an overall "
            f"quality score of {score.overall}/100. The most important findings are: {issue_phrase}."
        )
    else:
        executive_summary = (
            f"The dataset contains {profile.row_count} rows and {profile.column_count} columns with an overall "
            f"quality score of {score.overall}/100. No material data quality issues were detected by the MVP rules."
        )

    recommended_focus = [issue.recommendation for issue in top_issues] or [
        "Keep monitoring completeness, validity, and duplicate rates as new data arrives."
    ]

    return AuditSummary(
        executive_summary=executive_summary,
        recommended_focus=recommended_focus,
        risk_level=risk_level,
        llm_ready_context=context,
        source="rule_based",
        confidence=0.75,
        notable_patterns=[issue.title for issue in top_issues],
        remediation_plan=recommended_focus,
    )


def build_llm_context(
    profile: DatasetProfile,
    issues: list[QualityIssue],
    score: QualityScore,
) -> dict[str, Any]:
    severity_counts = Counter(issue.severity for issue in issues)
    category_counts = Counter(issue.category for issue in issues)
    top_issues = issues[:8]
    return {
        "row_count": profile.row_count,
        "column_count": profile.column_count,
        "duplicate_row_count": profile.duplicate_row_count,
        "score": score.model_dump(),
        "issue_counts_by_severity": dict(severity_counts),
        "issue_counts_by_category": dict(category_counts),
        "columns": [
            {
                "name": column.name,
                "inferred_type": column.inferred_type,
                "missing_rate": column.missing_rate,
                "unique_rate": column.unique_rate,
            }
            for column in profile.columns
        ],
        "top_issues": [issue.model_dump(exclude={"examples"}) for issue in top_issues],
    }


def generate_llm_summary(context: dict[str, Any]) -> LlmAuditSummary | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    schema = LlmAuditSummary.model_json_schema()
    prompt = (
        "You are a senior data quality analyst. Use only the supplied deterministic audit context. "
        "Do not invent issues, columns, row counts, or examples. Produce a concise executive summary, "
        "a prioritized focus list, notable patterns, and a remediation plan."
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(context, separators=(",", ":"))},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "data_quality_audit_summary",
                    "strict": True,
                    "schema": schema,
                },
            },
            temperature=0.2,
        )
        content = response.choices[0].message.content
        if not content:
            return None
        return LlmAuditSummary.model_validate_json(content)
    except Exception:
        return None
