from __future__ import annotations

import json
import os

from app.schemas import AnalystAnswer, AuditResult
from app.summaries import build_llm_context


def answer_question(audit: AuditResult, question: str) -> AnalystAnswer:
    profile_answer = answer_profile_question(audit, question)
    if profile_answer is not None:
        return profile_answer

    llm_answer = generate_llm_answer(audit, question)
    if llm_answer is not None:
        return llm_answer

    lowered = question.lower()
    supporting = [issue.id for issue in audit.issues[:5]]

    if "fix" in lowered or "clean" in lowered or "remed" in lowered:
        answer = (
            "Start with the highest-severity issues: deduplicate likely keys, correct invalid contact fields, "
            "then handle missing values and outliers. Use the remediation tab for draft Pandas and SQL actions."
        )
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
            f"The most important items are: {top}."
        )

    return AnalystAnswer(
        audit_id=audit.audit_id,
        question=question,
        answer=answer,
        supporting_issue_ids=supporting,
    )


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


def generate_llm_answer(audit: AuditResult, question: str) -> AnalystAnswer | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    context = build_llm_context(audit.profile, audit.issues, audit.score)
    prompt = (
        "You are a senior data quality analyst inside Data Reliability Copilot. "
        "Answer the user's question using only the supplied deterministic audit context. "
        "Do not invent columns, row counts, values, examples, or issues. "
        "Do not request or reveal raw row data. If the audit context is not enough, say what is missing. "
        "Keep the answer practical, specific, and concise for a business or data team user."
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "audit_context": context,
                        },
                        separators=(",", ":"),
                    ),
                },
            ],
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
