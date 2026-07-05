from __future__ import annotations

from app.schemas import DatasetProfile, QualityIssue, QualityScore


SEVERITY_PENALTIES = {
    "critical": 18,
    "high": 10,
    "medium": 5,
    "low": 2,
}


def score_audit(profile: DatasetProfile, issues: list[QualityIssue]) -> QualityScore:
    category_scores = {
        "completeness": 100,
        "validity": 100,
        "consistency": 100,
        "uniqueness": 100,
        "reliability": 100,
    }

    for issue in issues:
        penalty = SEVERITY_PENALTIES[issue.severity] * max(issue.affected_rate, 0.03)
        bucket = issue.category if issue.category in category_scores else "reliability"
        category_scores[bucket] = max(0, category_scores[bucket] - int(round(penalty * 10)))

    if profile.duplicate_row_count:
        category_scores["uniqueness"] = max(0, category_scores["uniqueness"] - min(25, profile.duplicate_row_count * 2))

    overall = int(round(sum(category_scores.values()) / len(category_scores)))
    explanation = (
        f"Overall score is {overall}/100 across completeness, validity, consistency, "
        "uniqueness, and reliability. Higher-severity issues and broader affected rates reduce the score most."
    )

    return QualityScore(
        overall=overall,
        completeness=category_scores["completeness"],
        validity=category_scores["validity"],
        consistency=category_scores["consistency"],
        uniqueness=category_scores["uniqueness"],
        reliability=category_scores["reliability"],
        explanation=explanation,
    )
