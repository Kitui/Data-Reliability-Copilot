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

    return AnalystAnswer(
        audit_id=audit.audit_id,
        question=question,
        answer=build_grounded_fallback_answer(audit, lowered),
        supporting_issue_ids=relevant_issue_ids(audit, lowered),
    )


def is_score_improvement_question(lowered: str) -> bool:
    return any(word in lowered for word in ["improve", "increase", "raise", "better", "boost"]) and any(
        word in lowered for word in ["score", "quality", "100"]
    )


def is_report_question(lowered: str) -> bool:
    return any(word in lowered for word in ["report", "tell", "present", "share"]) and any(
        word in lowered for word in ["data", "dataset", "audit", "manager", "stakeholder"]
    )


def is_ml_question(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in [
            "ml",
            "model",
            "training",
            "machine learning",
            "prediction",
            "predictive",
            "ai model",
            "segmentation",
        ]
    )


def is_risk_question(lowered: str) -> bool:
    return "risk" in lowered or "safest" in lowered or "least severe" in lowered or "lowest severity" in lowered


def build_grounded_fallback_answer(audit: AuditResult, lowered: str) -> str:
    column = find_referenced_column(audit, lowered)
    if column is not None:
        return build_column_overview_answer(audit, column.name)
    if is_score_improvement_question(lowered):
        return build_score_improvement_answer(audit)
    if is_risk_question(lowered):
        return build_risk_answer(audit, lowered)
    if is_ml_question(lowered):
        return build_ml_answer(audit)
    if is_report_question(lowered) or any(word in lowered for word in ["manager", "executive", "summary"]):
        return build_report_answer(audit)
    if any(word in lowered for word in ["fix", "clean", "remed", "repair", "correct"]):
        return build_fix_answer(audit)
    if any(word in lowered for word in ["rule", "contract", "schema", "governance", "validate"]):
        return build_contract_answer(audit)
    if any(word in lowered for word in ["privacy", "pii", "sensitive", "share", "mask", "protect"]):
        return build_privacy_answer(audit)
    if any(word in lowered for word in ["duplicate", "unique", "dedupe"]):
        return build_category_answer(audit, "uniqueness")
    if any(word in lowered for word in ["missing", "blank", "null", "complete", "completeness"]):
        return build_category_answer(audit, "completeness")
    if any(word in lowered for word in ["valid", "format", "email", "phone"]):
        return build_category_answer(audit, "validity")
    if any(word in lowered for word in ["outlier", "anomaly", "unusual"]):
        return build_category_answer(audit, "anomaly")
    if any(word in lowered for word in ["wrong", "problem", "issue", "bad", "quality"]):
        return build_issue_overview_answer(audit)
    return build_capability_answer(audit)


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


def build_risk_answer(audit: AuditResult, lowered: str) -> str:
    ordered = sorted(
        audit.issues,
        key=lambda issue: (severity_rank(issue.severity), issue.affected_rate, issue.confidence),
    )
    issue = ordered[0] if "least" in lowered or "lowest" in lowered or "safest" in lowered else ordered[-1]
    direction = "least risky" if issue == ordered[0] else "highest-risk"
    return (
        f"The {direction} issue is {issue.id}: {issue.title}. It is rated {issue.severity}, affects "
        f"{issue.affected_rows} rows ({issue.affected_rate:.0%}), and relates to {', '.join(issue.columns)}. "
        f"Recommendation: {issue.recommendation}"
    )


def build_ml_answer(audit: AuditResult) -> str:
    readiness = assess_ml_readiness(audit)
    blockers = " ".join(f"- {item}" for item in readiness.blockers) or "- No hard blockers detected."
    warnings = " ".join(f"- {item}" for item in readiness.warnings[:4]) or "- No major warnings detected."
    unsuitable = ", ".join(readiness.unsuitable_features) or "none flagged"
    return (
        f"Use this dataset for machine learning only after remediation. ML readiness is {readiness.score}/100 "
        f"with {readiness.risk_level} risk. Blockers: {blockers} Warnings: {warnings} "
        f"Features to exclude or protect before modeling: {unsuitable}. "
        "Rerun the audit after deduplication, validation, and PII handling."
    )


def build_column_overview_answer(audit: AuditResult, column_name: str) -> str:
    column = next(item for item in audit.profile.columns if item.name == column_name)
    related = [issue for issue in audit.issues if column.name in issue.columns]
    stats = safe_stats_text(column.stats)
    issue_text = (
        " Related issues: "
        + "; ".join(f"{issue.id} {issue.title} ({issue.severity})" for issue in related[:4])
        if related
        else " No issues are directly tied to this column."
    )
    return (
        f"{column.name} is inferred as {column.inferred_type}. It has {column.missing_count} missing values "
        f"({column.missing_rate:.0%}) and {column.unique_count} unique values ({column.unique_rate:.0%} uniqueness). "
        f"{stats}{issue_text}"
    )


def build_contract_answer(audit: AuditResult) -> str:
    contract = generate_contract(audit)
    required = ", ".join(contract.required_columns) or "none"
    pii = ", ".join(contract.pii_columns) or "none detected"
    allowed = ", ".join(contract.allowed_values.keys()) or "none inferred"
    return (
        "Use a data contract to prevent these problems from recurring. "
        f"Required columns should include: {required}. Expected types are defined for {len(contract.expected_types)} columns. "
        f"Controlled allowed-value fields: {allowed}. PII fields to protect: {pii}. "
        "After editing the contract, use it as rules for future uploads so schema drift, invalid values, and missing fields are caught earlier."
    )


def build_privacy_answer(audit: AuditResult) -> str:
    privacy_issues = [issue for issue in audit.issues if issue.category == "privacy"]
    pii_columns = sorted({column for issue in privacy_issues for column in issue.columns})
    if not pii_columns:
        return "No PII columns were flagged by the current audit rules, but review access controls before sharing production data."
    return (
        f"Treat {', '.join(pii_columns)} as sensitive before sharing or using this dataset with AI tools. "
        "Recommended controls: mask or hash values, restrict exports, avoid sending raw personal values to LLMs, "
        "and document these fields in the data contract."
    )


def build_category_answer(audit: AuditResult, category: str) -> str:
    issues = [issue for issue in audit.issues if issue.category == category]
    if not issues:
        return f"No {category} issues were detected by the current audit rules."
    issue_text = " ".join(
        f"{index}. {issue.id} {issue.title}: {issue.affected_rows} affected rows; {issue.recommendation}"
        for index, issue in enumerate(issues[:5], start=1)
    )
    return f"{category.title()} findings: {issue_text}"


def build_issue_overview_answer(audit: AuditResult) -> str:
    counts = {}
    for issue in audit.issues:
        counts[issue.category] = counts.get(issue.category, 0) + 1
    categories = ", ".join(f"{category}: {count}" for category, count in sorted(counts.items()))
    top = "; ".join(f"{issue.id} {issue.title} ({issue.severity})" for issue in audit.issues[:5])
    return (
        f"This dataset has {len(audit.issues)} detected issues across {categories}. "
        f"The current score is {audit.score.overall}/100 with {audit.summary.risk_level} risk. "
        f"Highest-priority findings: {top}."
    )


def build_capability_answer(audit: AuditResult) -> str:
    return (
        f"I can answer questions about this audit's score ({audit.score.overall}/100), risk level "
        f"({audit.summary.risk_level}), issues, columns, missing values, duplicates, outliers, PII, ML readiness, "
        "remediation actions, data contracts, and report summaries. Ask about a specific column, business use case, "
        "quality dimension, or next action and I will ground the answer in the audit results."
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


def relevant_issue_ids(audit: AuditResult, lowered: str) -> list[str]:
    column = find_referenced_column(audit, lowered)
    if column is not None:
        related = related_issue_ids(audit, column.name)
        if related:
            return related
    category_terms = {
        "uniqueness": ["duplicate", "unique", "dedupe"],
        "completeness": ["missing", "blank", "null", "complete"],
        "validity": ["valid", "format", "email", "phone"],
        "anomaly": ["outlier", "anomaly", "unusual"],
        "privacy": ["privacy", "pii", "sensitive", "share", "mask"],
    }
    for category, terms in category_terms.items():
        if any(term in lowered for term in terms):
            ids = [issue.id for issue in audit.issues if issue.category == category][:5]
            if ids:
                return ids
    return [issue.id for issue in audit.issues[:5]]


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


def safe_stats_text(stats: dict[str, object]) -> str:
    safe_keys = ["min", "max", "mean", "median"]
    parts = [f"{key}: {format_stat(stats[key])}" for key in safe_keys if key in stats]
    return "Stats: " + ", ".join(parts) + ". " if parts else ""


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
