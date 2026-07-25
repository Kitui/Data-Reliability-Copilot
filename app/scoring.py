from __future__ import annotations

import math
from collections import defaultdict

from app.schemas import DatasetProfile, QualityIssue, QualityScore, ScoreDeduction, ScoringContext

SEVERITY_WEIGHTS = {
    "critical": 24.0,
    "high": 14.0,
    "medium": 7.0,
    "low": 3.0,
}

CRITICALITY_MULTIPLIERS = {
    "low": 0.85,
    "medium": 1.0,
    "high": 1.15,
    "mission_critical": 1.3,
}

CATEGORY_BUCKETS = {
    "completeness": "completeness",
    "validity": "validity",
    "consistency": "consistency",
    "uniqueness": "uniqueness",
    "anomaly": "reliability",
    "schema": "reliability",
    "integrity": "reliability",
    "privacy": "reliability",
    "timeliness": "reliability",
}

INACTIVE_STATUSES = {"fixed", "resolved", "ignored"}


def _normalise_weights(context: ScoringContext) -> dict[str, float]:
    defaults = ScoringContext().dimension_weights
    weights = {key: max(float(context.dimension_weights.get(key, defaults[key])), 0.0) for key in defaults}
    total = sum(weights.values()) or 1.0
    return {key: value / total for key, value in weights.items()}


def _affected_factor(rate: float) -> float:
    """Progressive breadth factor that avoids tiny defects being ignored or broad defects exploding."""
    bounded = min(max(float(rate), 0.0), 1.0)
    return 0.18 + 0.82 * math.sqrt(bounded)


def score_audit(
    profile: DatasetProfile,
    issues: list[QualityIssue],
    context: ScoringContext | None = None,
) -> QualityScore:
    context = context or ScoringContext()
    weights = _normalise_weights(context)
    criticality = CRITICALITY_MULTIPLIERS[context.dataset_criticality]
    deductions_by_dimension: dict[str, float] = defaultdict(float)
    deductions: list[ScoreDeduction] = []
    active_count = 0
    accepted_count = 0

    for issue in issues:
        if issue.status in INACTIVE_STATUSES:
            continue
        active_count += 1
        status_multiplier = 1.0
        if issue.status == "accepted_risk":
            accepted_count += 1
            status_multiplier = context.accepted_risk_discount
        elif issue.status == "in_progress":
            status_multiplier = 0.9

        severity_weight = SEVERITY_WEIGHTS[issue.severity]
        breadth = _affected_factor(issue.affected_rate)
        confidence = 0.75 + 0.25 * float(issue.confidence)
        rule_multiplier = context.rule_issue_multiplier if issue.rule_id is not None else 1.0
        raw_penalty = severity_weight * breadth
        weighted_penalty = raw_penalty * confidence * rule_multiplier * criticality * status_multiplier
        bucket = CATEGORY_BUCKETS.get(issue.category, "reliability")
        deductions_by_dimension[bucket] += weighted_penalty
        deductions.append(ScoreDeduction(
            issue_id=issue.id,
            category=bucket,
            severity=issue.severity,
            status=issue.status,
            affected_rate=issue.affected_rate,
            raw_penalty=round(raw_penalty, 3),
            weighted_penalty=round(weighted_penalty, 3),
            reason=(
                f"{issue.severity.title()} severity affecting {issue.affected_rate:.1%} of rows"
                + ("; rule-backed finding" if issue.rule_id is not None else "")
                + ("; accepted-risk discount applied" if issue.status == "accepted_risk" else "")
            ),
        ))

    if profile.duplicate_row_rate > 0:
        duplicate_penalty = min(15.0, 4.0 + 18.0 * math.sqrt(profile.duplicate_row_rate)) * criticality
        deductions_by_dimension["uniqueness"] += duplicate_penalty

    dimension_scores = {
        name: max(0, min(100, int(round(100 - deductions_by_dimension.get(name, 0.0)))))
        for name in weights
    }
    overall = int(round(sum(dimension_scores[name] * weights[name] for name in weights)))
    total_penalty = round(sum(deductions_by_dimension.values()), 3)
    explanation = (
        f"Overall reliability is {overall}/100 using weighted quality dimensions and {context.dataset_criticality.replace('_', ' ')} "
        f"dataset criticality. Severity, affected-row breadth, confidence, rule-backed findings, and issue status determine deductions."
    )

    return QualityScore(
        overall=overall,
        completeness=dimension_scores["completeness"],
        validity=dimension_scores["validity"],
        consistency=dimension_scores["consistency"],
        uniqueness=dimension_scores["uniqueness"],
        reliability=dimension_scores["reliability"],
        explanation=explanation,
        dataset_criticality=context.dataset_criticality,
        active_issue_count=active_count,
        accepted_risk_count=accepted_count,
        total_weighted_penalty=total_penalty,
        dimension_weights=weights,
        deductions=sorted(deductions, key=lambda item: item.weighted_penalty, reverse=True),
    )
