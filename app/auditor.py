from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd

from app.profiler import profile_dataset
from app.rules import detect_issues
from app.quality_rules import execute_quality_rules
from app.schemas import AuditResult, AuditRuleConfig, RuleDefinition, UploadedFileInfo, ScoringContext
from app.scoring import score_audit
from app.summaries import summarize_audit


def audit_dataframe(
    frame: pd.DataFrame,
    dataset_name: str,
    rule_config: AuditRuleConfig | None = None,
    upload: UploadedFileInfo | None = None,
    quality_rules: list[RuleDefinition] | None = None,
    scoring_context: ScoringContext | None = None,
) -> AuditResult:
    rule_config = rule_config or AuditRuleConfig()
    profile = profile_dataset(frame)
    issues = detect_issues(frame, profile, rule_config)
    reusable_issues, rule_executions = execute_quality_rules(frame, quality_rules or [], starting_index=len(issues) + 1)
    issues.extend(reusable_issues)
    scoring_context = scoring_context or ScoringContext()
    score = score_audit(profile, issues, scoring_context)
    summary = summarize_audit(profile, issues, score)

    return AuditResult(
        audit_id=str(uuid4()),
        dataset_name=dataset_name,
        created_at=datetime.now(timezone.utc),
        upload=upload,
        rule_config=rule_config,
        profile=profile,
        issues=issues,
        rule_executions=rule_executions,
        score=score,
        scoring_context=scoring_context,
        summary=summary,
    )
