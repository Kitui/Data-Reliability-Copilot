from __future__ import annotations

from app.schemas import AnalystAnswer, AuditResult


def answer_question(audit: AuditResult, question: str) -> AnalystAnswer:
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
