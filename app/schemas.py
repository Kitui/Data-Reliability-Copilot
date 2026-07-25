from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Severity = Literal["low", "medium", "high", "critical"]
IssueStatus = Literal["open", "triaged", "in_progress", "blocked", "resolved", "fixed", "accepted_risk", "ignored", "reopened"]
IssueCategory = Literal[
    "completeness",
    "validity",
    "uniqueness",
    "consistency",
    "anomaly",
    "schema",
    "integrity",
    "privacy",
    "timeliness",
]


class ColumnProfile(BaseModel):
    name: str
    inferred_type: str
    missing_count: int
    missing_rate: float
    unique_count: int
    unique_rate: float
    sample_values: list[str]
    stats: dict[str, Any] = Field(default_factory=dict)
    cardinality: str = "unknown"
    constant: bool = False
    identifier_candidate: bool = False
    outlier_count: int = 0
    outlier_rate: float = 0.0
    risk_score: int = 0
    risk_level: Literal["low", "medium", "high"] = "low"
    signals: list[str] = Field(default_factory=list)
    privacy_classification: str | None = None
    sensitivity: Literal["low", "medium", "high", "critical"] | None = None
    privacy_confidence: float = 0.0
    privacy_reasons: list[str] = Field(default_factory=list)
    masking_recommendation: str | None = None


class DatasetProfile(BaseModel):
    row_count: int
    column_count: int
    duplicate_row_count: int
    columns: list[ColumnProfile]
    completeness_rate: float = 1.0
    duplicate_row_rate: float = 0.0
    high_risk_column_count: int = 0
    medium_risk_column_count: int = 0
    sensitive_column_count: int = 0
    highest_sensitivity: Literal["low", "medium", "high", "critical"] = "low"


class QualityIssue(BaseModel):
    id: str
    category: IssueCategory
    severity: Severity
    title: str
    detail: str
    columns: list[str]
    affected_rows: int
    affected_rate: float
    examples: list[dict[str, Any]] = Field(default_factory=list)
    recommendation: str
    confidence: float = Field(ge=0, le=1)
    status: IssueStatus = "open"
    owner: str | None = None
    resolution_note: str | None = None
    rule_id: int | None = None
    rule_name: str | None = None
    assigned_user_id: int | None = None
    due_date: date | None = None
    resolution_evidence: str | None = None
    updated_at: datetime | None = None


class ScoreDeduction(BaseModel):
    issue_id: str
    category: str
    severity: Severity
    status: IssueStatus
    affected_rate: float
    raw_penalty: float
    weighted_penalty: float
    reason: str


class ScoringContext(BaseModel):
    dataset_criticality: Literal["low", "medium", "high", "mission_critical"] = "medium"
    accepted_risk_discount: float = Field(default=0.25, ge=0, le=1)
    rule_issue_multiplier: float = Field(default=1.1, ge=0.5, le=3)
    dimension_weights: dict[str, float] = Field(default_factory=lambda: {
        "completeness": 0.24,
        "validity": 0.22,
        "consistency": 0.16,
        "uniqueness": 0.16,
        "reliability": 0.22,
    })


class QualityScore(BaseModel):
    overall: int
    completeness: int
    validity: int
    consistency: int
    uniqueness: int
    reliability: int
    explanation: str
    dataset_criticality: Literal["low", "medium", "high", "mission_critical"] = "medium"
    active_issue_count: int = 0
    accepted_risk_count: int = 0
    total_weighted_penalty: float = 0.0
    dimension_weights: dict[str, float] = Field(default_factory=dict)
    deductions: list[ScoreDeduction] = Field(default_factory=list)


class AuditSummary(BaseModel):
    executive_summary: str
    recommended_focus: list[str]
    risk_level: Literal["low", "medium", "high", "critical"]
    llm_ready_context: dict[str, Any]
    source: Literal["rule_based", "llm"] = "rule_based"
    model: str | None = None
    confidence: float = Field(default=0.75, ge=0, le=1)
    notable_patterns: list[str] = Field(default_factory=list)
    remediation_plan: list[str] = Field(default_factory=list)


class DateRangeRule(BaseModel):
    min: str | None = None
    max: str | None = None


class NumericRangeRule(BaseModel):
    min: float | None = None
    max: float | None = None


class AuditRuleConfig(BaseModel):
    required_columns: list[str] = Field(default_factory=list)
    unique_columns: list[str] = Field(default_factory=list)
    expected_types: dict[str, Literal["numeric", "datetime", "text", "boolean"]] = Field(default_factory=dict)
    allowed_values: dict[str, list[str]] = Field(default_factory=dict)
    date_ranges: dict[str, DateRangeRule] = Field(default_factory=dict)
    numeric_ranges: dict[str, NumericRangeRule] = Field(default_factory=dict)
    stale_after_days: dict[str, int] = Field(default_factory=dict)


RuleType = Literal["required", "unique", "email", "allowed_values", "regex", "numeric_range", "length_range", "missing_threshold", "expected_type", "stale_days", "duplicate_rows"]
RuleOutcome = Literal["passed", "failed", "warning", "skipped"]


class RuleDefinition(BaseModel):
    id: int | None = None
    name: str
    description: str | None = None
    rule_type: RuleType
    scope: Literal["dataset", "column"] = "column"
    column_name: str | None = None
    category: IssueCategory = "validity"
    severity: Severity = "medium"
    parameters: dict[str, Any] = Field(default_factory=dict)
    recommendation: str | None = None
    is_active: bool = True


class RuleExecution(BaseModel):
    rule_id: int | None = None
    rule_name: str
    rule_type: RuleType
    outcome: RuleOutcome
    affected_rows: int = 0
    affected_rate: float = 0.0
    message: str
    executed_at: datetime


class UploadedFileInfo(BaseModel):
    original_filename: str
    stored_filename: str
    path: str
    size_bytes: int
    content_type: str | None = None
    storage_backend: str = "local"
    checksum_sha256: str | None = None
    display_name: str | None = None


class LlmAuditSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: str = Field(min_length=40, max_length=900)
    recommended_focus: list[str] = Field(min_length=1, max_length=5)
    risk_level: Literal["low", "medium", "high", "critical"]
    notable_patterns: list[str] = Field(min_length=1, max_length=5)
    remediation_plan: list[str] = Field(min_length=1, max_length=6)
    confidence: float = Field(ge=0, le=1)

    @field_validator("recommended_focus", "notable_patterns", "remediation_plan")
    @classmethod
    def reject_empty_items(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if not cleaned:
            raise ValueError("At least one non-empty item is required.")
        return cleaned


class AuditResult(BaseModel):
    audit_id: str
    dataset_name: str
    created_at: datetime
    audit_kind: Literal["dataset_import", "version_import", "rerun", "scheduled", "sample", "remediation", "audit"] = "audit"
    dataset_version: int | None = Field(default=None, ge=1)
    upload: UploadedFileInfo | None = None
    rule_config: AuditRuleConfig = Field(default_factory=AuditRuleConfig)
    profile: DatasetProfile
    issues: list[QualityIssue]
    rule_executions: list[RuleExecution] = Field(default_factory=list)
    score: QualityScore
    scoring_context: ScoringContext = Field(default_factory=ScoringContext)
    summary: AuditSummary




class ScoreRecalculationRequest(BaseModel):
    dataset_criticality: Literal["low", "medium", "high", "mission_critical"] | None = None
    accepted_risk_discount: float | None = Field(default=None, ge=0, le=1)
    rule_issue_multiplier: float | None = Field(default=None, ge=0.5, le=3)

class AppliedRecommendation(BaseModel):
    audit_id: str
    issue_id: str
    status: Literal["applied"] = "applied"
    previous_score: int
    updated_score: int
    score_improvement: int
    resolution_note: str
    audit: AuditResult


class AuditListItem(BaseModel):
    audit_id: str
    dataset_name: str
    created_at: datetime
    score: int
    risk_level: Literal["low", "medium", "high", "critical"]
    issue_count: int
    summary_source: Literal["rule_based", "llm"]


class IssueStatusUpdate(BaseModel):
    status: IssueStatus | None = None
    owner: str | None = None
    assigned_user_id: int | None = None
    severity: Severity | None = None
    due_date: date | None = None
    resolution_note: str | None = None
    resolution_evidence: str | None = None


class IssueCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class IssueLifecycleActivity(BaseModel):
    id: int
    audit_id: str
    issue_id: str
    action: str
    field_name: str | None = None
    previous_value: str | None = None
    new_value: str | None = None
    note: str | None = None
    actor_user_id: int | None = None
    actor_name: str | None = None
    created_at: datetime


class IssueLifecycleDetail(BaseModel):
    issue: QualityIssue
    activities: list[IssueLifecycleActivity] = Field(default_factory=list)


class RemediationAction(BaseModel):
    issue_id: str
    title: str
    action_type: Literal["deduplicate", "fill_missing", "standardize", "validate", "mask", "review", "contract"]
    description: str
    pandas_code: str
    sql_hint: str
    risk: Literal["low", "medium", "high"]
    requires_review: bool = True


class RemediationPlan(BaseModel):
    audit_id: str
    actions: list[RemediationAction]
    generated_cleaning_script: str


class RemediationRequest(BaseModel):
    issue_ids: list[str] = Field(default_factory=list)
    fill_strategy: Literal["mode", "blank", "zero"] = "mode"
    mask_sensitive: bool = True


class RemediationPreview(BaseModel):
    audit_id: str
    selected_actions: int
    rows_before: int
    rows_after: int
    columns_before: int
    columns_after: int
    score_before: int
    projected_score: int
    projected_score_delta: int
    issues_before: int
    projected_issues: int
    changed_cells: int
    removed_rows: int
    changed_columns: list[str]
    sample_changes: list[dict[str, object]]
    warnings: list[str]


class RemediationApplyResult(BaseModel):
    source_audit_id: str
    corrected_audit: AuditResult
    download_url: str
    applied_actions: int
    changed_cells: int
    removed_rows: int


class DataContract(BaseModel):
    dataset_name: str
    generated_from_audit_id: str
    required_columns: list[str]
    unique_columns: list[str]
    expected_types: dict[str, Literal["numeric", "datetime", "text", "boolean"]]
    allowed_values: dict[str, list[str]]
    numeric_ranges: dict[str, NumericRangeRule]
    date_ranges: dict[str, DateRangeRule]
    pii_columns: list[str]
    freshness_rules: dict[str, int] = Field(default_factory=dict)
    format_rules: dict[str, dict[str, object]] = Field(default_factory=dict)
    length_ranges: dict[str, dict[str, int | None]] = Field(default_factory=dict)
    missing_thresholds: dict[str, float] = Field(default_factory=dict)
    assigned_rule_sources: list[dict[str, object]] = Field(default_factory=list)
    profile_summary: dict[str, object] = Field(default_factory=dict)


class ComparisonIssueChange(BaseModel):
    title: str
    category: IssueCategory
    severity: Severity
    columns: list[str]


class AuditComparison(BaseModel):
    baseline_audit_id: str
    candidate_audit_id: str
    score_delta: int
    issue_count_delta: int
    row_count_delta: int = 0
    column_count_delta: int = 0
    new_issues: list[ComparisonIssueChange]
    resolved_issues: list[ComparisonIssueChange]
    persistent_issues: list[ComparisonIssueChange] = Field(default_factory=list)
    worsened_columns: list[str]
    improved_columns: list[str]
    schema_changes: dict[str, list[str]]
    type_changes: list[dict[str, str]] = Field(default_factory=list)


class MlReadiness(BaseModel):
    audit_id: str
    score: int
    risk_level: Literal["low", "medium", "high", "critical"]
    blockers: list[str]
    warnings: list[str]
    recommended_target_checks: list[str]
    unsuitable_features: list[str]


class AnalystChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=2000)


class AnalystQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    history: list[AnalystChatMessage] = Field(default_factory=list, max_length=12)


class AnalystAnswer(BaseModel):
    audit_id: str
    question: str
    answer: str
    source: Literal["rule_based", "llm"] = "rule_based"
    supporting_issue_ids: list[str] = Field(default_factory=list)
