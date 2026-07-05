from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Severity = Literal["low", "medium", "high", "critical"]
IssueStatus = Literal["open", "ignored", "in_progress", "fixed", "accepted_risk"]
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


class DatasetProfile(BaseModel):
    row_count: int
    column_count: int
    duplicate_row_count: int
    columns: list[ColumnProfile]


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


class QualityScore(BaseModel):
    overall: int
    completeness: int
    validity: int
    consistency: int
    uniqueness: int
    reliability: int
    explanation: str


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


class UploadedFileInfo(BaseModel):
    original_filename: str
    stored_filename: str
    path: str
    size_bytes: int
    content_type: str | None = None


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
    upload: UploadedFileInfo | None = None
    rule_config: AuditRuleConfig = Field(default_factory=AuditRuleConfig)
    profile: DatasetProfile
    issues: list[QualityIssue]
    score: QualityScore
    summary: AuditSummary


class AuditListItem(BaseModel):
    audit_id: str
    dataset_name: str
    created_at: datetime
    score: int
    risk_level: Literal["low", "medium", "high", "critical"]
    issue_count: int
    summary_source: Literal["rule_based", "llm"]


class IssueStatusUpdate(BaseModel):
    status: IssueStatus
    owner: str | None = None
    resolution_note: str | None = None


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
    new_issues: list[ComparisonIssueChange]
    resolved_issues: list[ComparisonIssueChange]
    worsened_columns: list[str]
    improved_columns: list[str]
    schema_changes: dict[str, list[str]]


class MlReadiness(BaseModel):
    audit_id: str
    score: int
    risk_level: Literal["low", "medium", "high", "critical"]
    blockers: list[str]
    warnings: list[str]
    recommended_target_checks: list[str]
    unsuitable_features: list[str]


class AnalystQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class AnalystAnswer(BaseModel):
    audit_id: str
    question: str
    answer: str
    source: Literal["rule_based", "llm"] = "rule_based"
    supporting_issue_ids: list[str] = Field(default_factory=list)
