from __future__ import annotations

from app.schemas import AuditComparison, AuditResult, ComparisonIssueChange


def compare_audits(baseline: AuditResult, candidate: AuditResult) -> AuditComparison:
    baseline_issues = {_issue_key(issue): issue for issue in baseline.issues}
    candidate_issues = {_issue_key(issue): issue for issue in candidate.issues}
    baseline_columns = {column.name: column for column in baseline.profile.columns}
    candidate_columns = {column.name: column for column in candidate.profile.columns}

    new_keys = candidate_issues.keys() - baseline_issues.keys()
    resolved_keys = baseline_issues.keys() - candidate_issues.keys()
    persistent_keys = baseline_issues.keys() & candidate_issues.keys()
    shared_columns = baseline_columns.keys() & candidate_columns.keys()

    worsened = [
        column
        for column in shared_columns
        if candidate_columns[column].missing_rate > baseline_columns[column].missing_rate
    ]
    improved = [
        column
        for column in shared_columns
        if candidate_columns[column].missing_rate < baseline_columns[column].missing_rate
    ]

    return AuditComparison(
        baseline_audit_id=baseline.audit_id,
        candidate_audit_id=candidate.audit_id,
        score_delta=candidate.score.overall - baseline.score.overall,
        issue_count_delta=len(candidate.issues) - len(baseline.issues),
        row_count_delta=candidate.profile.row_count - baseline.profile.row_count,
        column_count_delta=candidate.profile.column_count - baseline.profile.column_count,
        new_issues=[_change(candidate_issues[key]) for key in sorted(new_keys)],
        resolved_issues=[_change(baseline_issues[key]) for key in sorted(resolved_keys)],
        persistent_issues=[_change(candidate_issues[key]) for key in sorted(persistent_keys)],
        worsened_columns=worsened,
        improved_columns=improved,
        schema_changes={
            "added_columns": sorted(candidate_columns.keys() - baseline_columns.keys()),
            "removed_columns": sorted(baseline_columns.keys() - candidate_columns.keys()),
        },
        type_changes=[
            {"column": name, "before": str(baseline_columns[name].inferred_type), "after": str(candidate_columns[name].inferred_type)}
            for name in sorted(shared_columns)
            if baseline_columns[name].inferred_type != candidate_columns[name].inferred_type
        ],
    )


def _issue_key(issue) -> tuple[str, tuple[str, ...]]:
    return issue.title, tuple(issue.columns)


def _change(issue) -> ComparisonIssueChange:
    return ComparisonIssueChange(
        title=issue.title,
        category=issue.category,
        severity=issue.severity,
        columns=issue.columns,
    )
