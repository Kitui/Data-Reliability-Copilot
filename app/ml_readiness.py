from __future__ import annotations

from app.schemas import AuditResult, MlReadiness


def assess_ml_readiness(audit: AuditResult) -> MlReadiness:
    blockers: list[str] = []
    warnings: list[str] = []
    unsuitable_features: list[str] = []

    for issue in audit.issues:
        if issue.severity in {"critical", "high"} and issue.category in {"schema", "uniqueness", "privacy"}:
            blockers.append(f"{issue.title}: {issue.recommendation}")
        elif issue.category in {"anomaly", "completeness", "validity"}:
            warnings.append(f"{issue.title}: {issue.affected_rows} affected rows")

    for column in audit.profile.columns:
        if column.missing_rate > 0.3:
            unsuitable_features.append(column.name)
        elif column.unique_rate > 0.95 and column.inferred_type == "text":
            unsuitable_features.append(column.name)
        elif column.name.lower() in {"id", "customer_id", "user_id", "email", "phone", "name"}:
            unsuitable_features.append(column.name)

    penalty = min(60, len(blockers) * 15 + len(warnings) * 4 + len(set(unsuitable_features)) * 2)
    score = max(0, audit.score.overall - penalty)
    if score < 50 or blockers:
        risk_level = "critical"
    elif score < 70:
        risk_level = "high"
    elif score < 85:
        risk_level = "medium"
    else:
        risk_level = "low"

    return MlReadiness(
        audit_id=audit.audit_id,
        score=score,
        risk_level=risk_level,
        blockers=blockers,
        warnings=warnings,
        recommended_target_checks=[
            "Confirm the prediction target column is present and not missing.",
            "Check class balance or target distribution before training.",
            "Scan for target leakage from timestamps, status fields, or post-outcome columns.",
        ],
        unsuitable_features=sorted(set(unsuitable_features)),
    )
