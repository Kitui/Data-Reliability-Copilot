from __future__ import annotations

import json
import os

from app.contracts import generate_contract
from app.ml_readiness import assess_ml_readiness
from app.remediation import build_remediation_plan
from app.schemas import AnalystAnswer, AnalystChatMessage, AuditResult
from app.summaries import build_llm_context


def answer_question(
    audit: AuditResult,
    question: str,
    history: list[AnalystChatMessage] | None = None,
) -> AnalystAnswer:
    profile_answer = answer_profile_question(audit, question)
    if profile_answer is not None:
        return profile_answer

    llm_answer = generate_llm_answer(audit, question, history or [])
    if llm_answer is not None:
        return llm_answer

    lowered = question.lower()
    supporting = [issue.id for issue in audit.issues[:5]]

    if is_score_improvement_question(lowered):
        answer = build_score_improvement_answer(audit)
    elif is_report_question(lowered):
        answer = build_report_answer(audit)
    elif "fix" in lowered or "clean" in lowered or "remed" in lowered:
        answer = build_fix_answer(audit)
    elif "manager" in lowered or "executive" in lowered or "summary" in lowered:
        answer = audit.summary.executive_summary
    elif "ml" in lowered or "model" in lowered or "training" in lowered:
        answer = (
            "For ML use, treat PII, duplicate entity keys, high-cardinality identifiers, missing target-like fields, "
            "and outliers as blockers or warnings before training."
        )
    elif "rule" in lowered or "contract" in lowered:
        answer = (
            "Generate a data contract from this audit, then tighten required columns, unique keys, allowed values, "
            "numeric ranges, date ranges, and freshness thresholds for future uploads."
        )
    else:
        top = "; ".join(f"{issue.title} ({issue.severity})" for issue in audit.issues[:3])
        answer = (
            f"This audit has score {audit.score.overall}/100 with {len(audit.issues)} issues. "
            f"The most important items are: {top}. Ask about a specific column, score, report, ML readiness, "
            "contract rules, or remediation plan for a more targeted answer."
        )

    return AnalystAnswer(
        audit_id=audit.audit_id,
        question=question,
        answer=answer,
        supporting_issue_ids=supporting,
    )


def is_score_improvement_question(lowered: str) -> bool:
    return any(word in lowered for word in ["improve", "increase", "raise", "better", "boost"]) and any(
        word in lowered for word in ["score", "quality", "100"]
    )


def is_report_question(lowered: str) -> bool:
    return any(word in lowered for word in ["report", "tell", "present", "share"]) and any(
        word in lowered for word in ["data", "dataset", "audit", "manager", "stakeholder"]
    )


def build_score_improvement_answer(audit: AuditResult) -> str:
    top_issues = sorted(
        audit.issues,
        key=lambda issue: (severity_rank(issue.severity), issue.affected_rate, issue.confidence),
        reverse=True,
    )[:5]
    actions = [f"{index}. {issue.recommendation}" for index, issue in enumerate(top_issues, start=1)]
    blockers = "; ".join(f"{issue.id} {issue.title}" for issue in top_issues[:3])
    return (
        f"To move from {audit.score.overall}/100 toward 100, fix the highest-impact issues first: {blockers}. "
        "Recommended order: "
        + " ".join(actions)
        + " After fixing, rerun the audit and compare the new score against this baseline."
    )


def build_report_answer(audit: AuditResult) -> str:
    high_count = sum(1 for issue in audit.issues if issue.severity in {"critical", "high"})
    categories = sorted({issue.category for issue in audit.issues})
    focus = " ".join(f"- {item}" for item in audit.summary.recommended_focus[:3])
    return (
        f"Report this dataset as {audit.summary.risk_level} risk with a {audit.score.overall}/100 quality score. "
        f"It has {len(audit.issues)} detected issues, including {high_count} high-priority items. "
        f"The main affected quality areas are: {', '.join(categories)}. "
        f"Executive summary: {audit.summary.executive_summary} "
        f"Recommended talking points: {focus}"
    )


def build_fix_answer(audit: AuditResult) -> str:
    top_issues = audit.issues[:3]
    issue_text = "; ".join(f"{issue.id} {issue.title}" for issue in top_issues)
    return (
        f"Start with these highest-priority issues: {issue_text}. "
        "Deduplicate likely keys first, correct invalid contact fields, then handle missing values and outliers. "
        "Use the remediation tab for draft Pandas and SQL actions."
    )


def severity_rank(severity: str) -> int:
    return {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(severity, 0)


def answer_profile_question(audit: AuditResult, question: str) -> AnalystAnswer | None:
    lowered = question.lower()
    column = find_referenced_column(audit, lowered)
    if column is None:
        return None

    stats = column.stats or {}
    metric: str | None = None
    label: str | None = None

    if any(word in lowered for word in ["highest", "maximum", "max", "largest", "biggest"]):
        metric = "max"
        label = "highest"
    elif any(word in lowered for word in ["lowest", "minimum", "min", "smallest"]):
        metric = "min"
        label = "lowest"
    elif any(word in lowered for word in ["average", "mean"]):
        metric = "mean"
        label = "average"
    elif "median" in lowered:
        metric = "median"
        label = "median"
    elif "missing" in lowered:
        return AnalystAnswer(
            audit_id=audit.audit_id,
            question=question,
            answer=(
                f"{column.name} has {column.missing_count} missing values "
                f"({column.missing_rate:.0%} of {audit.profile.row_count} rows)."
            ),
            supporting_issue_ids=related_issue_ids(audit, column.name),
        )
    elif "unique" in lowered or "distinct" in lowered:
        return AnalystAnswer(
            audit_id=audit.audit_id,
            question=question,
            answer=(
                f"{column.name} has {column.unique_count} unique values "
                f"({column.unique_rate:.0%} uniqueness across {audit.profile.row_count} rows)."
            ),
            supporting_issue_ids=related_issue_ids(audit, column.name),
        )

    if metric is None:
        return None
    if metric not in stats:
        return AnalystAnswer(
            audit_id=audit.audit_id,
            question=question,
            answer=f"I do not have a {label} value for {column.name}. The inferred type is {column.inferred_type}.",
            supporting_issue_ids=related_issue_ids(audit, column.name),
        )

    return AnalystAnswer(
        audit_id=audit.audit_id,
        question=question,
        answer=f"The {label} {column.name} is {format_stat(stats[metric])}.",
        supporting_issue_ids=related_issue_ids(audit, column.name),
    )


def find_referenced_column(audit: AuditResult, lowered_question: str):
    compact_question = normalize_name(lowered_question)
    for column in audit.profile.columns:
        column_name = column.name.lower()
        readable_name = column_name.replace("_", " ")
        if column_name in lowered_question or readable_name in lowered_question:
            return column
        if normalize_name(column_name) in compact_question:
            return column
    return None


def related_issue_ids(audit: AuditResult, column_name: str) -> list[str]:
    return [issue.id for issue in audit.issues if column_name in issue.columns][:5]


def normalize_name(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def format_stat(value: object) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def generate_llm_answer(
    audit: AuditResult,
    question: str,
    history: list[AnalystChatMessage],
) -> AnalystAnswer | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    context = build_analyst_context(audit)
    prompt = (
        "You are a senior data quality analyst inside Data Reliability Copilot. "
        "Answer each user question freshly and specifically using only the supplied deterministic audit context. "
        "Use the conversation history for references such as 'that column' or 'the previous issue'. "
        "Do not invent columns, row counts, values, examples, issues, or business facts. "
        "Do not request, reveal, or pretend to inspect raw row data. "
        "If exact aggregate values are available, cite them. If context is insufficient, say exactly what is missing. "
        "Keep answers practical, conversational, and specific to this dataset."
    )
    messages = [{"role": "system", "content": prompt}]
    messages.extend(
        {
            "role": message.role,
            "content": message.text,
        }
        for message in history[-8:]
    )
    messages.append(
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": question,
                    "audit_context": context,
                },
                separators=(",", ":"),
            ),
        }
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
            temperature=0.2,
        )
        answer = response.choices[0].message.content
        if not answer:
            return None
        return AnalystAnswer(
            audit_id=audit.audit_id,
            question=question,
            answer=answer.strip(),
            source="llm",
            supporting_issue_ids=[issue.id for issue in audit.issues[:5]],
        )
    except Exception:
        return None


def build_analyst_context(audit: AuditResult) -> dict[str, object]:
    remediation = build_remediation_plan(audit)
    contract = generate_contract(audit)
    ml_readiness = assess_ml_readiness(audit)
    base_context = build_llm_context(audit.profile, audit.issues, audit.score)
    return {
        **base_context,
        "dataset_name": audit.dataset_name,
        "created_at": audit.created_at.isoformat(),
        "summary": {
            "executive_summary": audit.summary.executive_summary,
            "recommended_focus": audit.summary.recommended_focus,
            "risk_level": audit.summary.risk_level,
            "notable_patterns": audit.summary.notable_patterns,
            "remediation_plan": audit.summary.remediation_plan,
        },
        "rule_config": audit.rule_config.model_dump(mode="json"),
        "remediation_actions": [
            {
                "issue_id": action.issue_id,
                "title": action.title,
                "action_type": action.action_type,
                "description": action.description,
                "risk": action.risk,
                "requires_review": action.requires_review,
                "sql_hint": action.sql_hint,
                "pandas_code": action.pandas_code,
            }
            for action in remediation.actions
        ],
        "data_contract": contract.model_dump(mode="json"),
        "ml_readiness": ml_readiness.model_dump(mode="json"),
    }
