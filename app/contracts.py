from __future__ import annotations

from typing import Iterable

from app.schemas import (
    AuditResult,
    AuditRuleConfig,
    DataContract,
    DateRangeRule,
    NumericRangeRule,
    RuleDefinition,
)


def generate_contract(audit: AuditResult, assigned_rules: Iterable[RuleDefinition] | None = None) -> DataContract:
    """Generate a contract from the audited schema and, when supplied, assigned governance rules.

    Dataset profiling remains useful context, but observed bad values must not silently become
    approved governance thresholds. When active assigned rules are supplied, only those rules
    define enforceable required, unique, allowed-value, range, format, and freshness constraints.
    """
    rules = [rule for rule in (assigned_rules or []) if rule.is_active]
    columns = {column.name: column for column in audit.profile.columns}
    expected_types = {
        column.name: _contract_type(column.inferred_type)
        for column in audit.profile.columns
        if column.inferred_type in {"numeric", "datetime", "text", "boolean"}
    }
    pii_columns = sorted({column for issue in audit.issues if issue.category == "privacy" for column in issue.columns})

    profile_summary = {
        "row_count": audit.profile.row_count,
        "column_count": audit.profile.column_count,
        "observed_unique_candidates": [
            column.name for column in audit.profile.columns
            if column.unique_rate >= 0.98 and column.missing_rate == 0
        ],
        "observed_allowed_values": {
            column.name: [item["value"] for item in column.stats.get("top_values", [])]
            for column in audit.profile.columns
            if column.inferred_type == "text" and 1 < column.unique_count <= 20
        },
        "observed_numeric_ranges": {
            column.name: {"min": column.stats["min"], "max": column.stats["max"]}
            for column in audit.profile.columns
            if column.inferred_type == "numeric" and {"min", "max"} <= set(column.stats)
        },
        "observed_date_ranges": {
            column.name: {"min": column.stats["min"], "max": column.stats["max"]}
            for column in audit.profile.columns
            if column.inferred_type == "datetime" and {"min", "max"} <= set(column.stats)
        },
    }

    # Backward-compatible profile-only generation for callers that do not supply assignments.
    if not rules:
        unique_columns = profile_summary["observed_unique_candidates"]
        allowed_values = profile_summary["observed_allowed_values"]
        numeric_ranges = {
            name: NumericRangeRule(**bounds)
            for name, bounds in profile_summary["observed_numeric_ranges"].items()
        }
        date_ranges = {
            name: DateRangeRule(**bounds)
            for name, bounds in profile_summary["observed_date_ranges"].items()
        }
        return DataContract(
            dataset_name=audit.dataset_name,
            generated_from_audit_id=audit.audit_id,
            required_columns=[column.name for column in audit.profile.columns if column.missing_rate == 0],
            unique_columns=unique_columns,
            expected_types=expected_types,
            allowed_values=allowed_values,
            numeric_ranges=numeric_ranges,
            date_ranges=date_ranges,
            pii_columns=pii_columns,
            profile_summary=profile_summary,
        )

    required_columns: list[str] = []
    unique_columns: list[str] = []
    allowed_values: dict[str, list[str]] = {}
    numeric_ranges: dict[str, NumericRangeRule] = {}
    date_ranges: dict[str, DateRangeRule] = {}
    freshness_rules: dict[str, int] = {}
    format_rules: dict[str, dict[str, object]] = {}
    length_ranges: dict[str, dict[str, int | None]] = {}
    missing_thresholds: dict[str, float] = {}
    rule_sources: list[dict[str, object]] = []

    for rule in rules:
        column = rule.column_name
        params = rule.parameters or {}
        rule_sources.append({
            "rule_id": rule.id,
            "name": rule.name,
            "rule_type": rule.rule_type,
            "column": column,
            "severity": rule.severity,
        })
        if rule.rule_type == "duplicate_rows":
            continue
        if not column or column not in columns:
            # Keep generation safe: stale/mistyped assignments cannot create phantom schema fields.
            continue
        if rule.rule_type == "required":
            _append_unique(required_columns, column)
        elif rule.rule_type == "unique":
            _append_unique(unique_columns, column)
        elif rule.rule_type == "email":
            format_rules[column] = {"format": "email"}
        elif rule.rule_type == "regex" and params.get("pattern") is not None:
            format_rules[column] = {"pattern": str(params["pattern"])}
        elif rule.rule_type == "allowed_values":
            allowed_values[column] = [str(value) for value in params.get("values", [])]
        elif rule.rule_type == "numeric_range":
            numeric_ranges[column] = NumericRangeRule(min=params.get("min"), max=params.get("max"))
        elif rule.rule_type == "length_range":
            length_ranges[column] = {"min": params.get("min"), "max": params.get("max")}
        elif rule.rule_type == "missing_threshold" and params.get("max_rate") is not None:
            missing_thresholds[column] = float(params["max_rate"])
        elif rule.rule_type == "expected_type" and params.get("type") in {"numeric", "datetime", "text", "boolean"}:
            expected_types[column] = params["type"]
        elif rule.rule_type == "stale_days" and params.get("days") is not None:
            freshness_rules[column] = int(params["days"])

    return DataContract(
        dataset_name=audit.dataset_name,
        generated_from_audit_id=audit.audit_id,
        required_columns=required_columns,
        unique_columns=unique_columns,
        expected_types=expected_types,
        allowed_values=allowed_values,
        numeric_ranges=numeric_ranges,
        date_ranges=date_ranges,
        pii_columns=pii_columns,
        freshness_rules=freshness_rules,
        format_rules=format_rules,
        length_ranges=length_ranges,
        missing_thresholds=missing_thresholds,
        assigned_rule_sources=rule_sources,
        profile_summary=profile_summary,
    )


def contract_to_rule_config(contract: DataContract) -> AuditRuleConfig:
    return AuditRuleConfig(
        required_columns=contract.required_columns,
        unique_columns=contract.unique_columns,
        expected_types=contract.expected_types,
        allowed_values=contract.allowed_values,
        numeric_ranges=contract.numeric_ranges,
        date_ranges=contract.date_ranges,
        stale_after_days=contract.freshness_rules,
    )


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _contract_type(inferred_type: str) -> str:
    return "text" if inferred_type == "empty" else inferred_type
