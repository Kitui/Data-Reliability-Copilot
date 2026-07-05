from __future__ import annotations

from app.schemas import AuditResult, AuditRuleConfig, DataContract, DateRangeRule, NumericRangeRule


def generate_contract(audit: AuditResult) -> DataContract:
    expected_types = {
        column.name: _contract_type(column.inferred_type)
        for column in audit.profile.columns
        if column.inferred_type in {"numeric", "datetime", "text", "boolean"}
    }
    unique_columns = [
        column.name
        for column in audit.profile.columns
        if column.unique_rate >= 0.98 and column.missing_rate == 0
    ]
    allowed_values = {
        column.name: [item["value"] for item in column.stats.get("top_values", [])]
        for column in audit.profile.columns
        if column.inferred_type == "text" and 1 < column.unique_count <= 20
    }
    numeric_ranges: dict[str, NumericRangeRule] = {}
    date_ranges: dict[str, DateRangeRule] = {}
    for column in audit.profile.columns:
        if column.inferred_type == "numeric" and {"min", "max"} <= set(column.stats):
            numeric_ranges[column.name] = NumericRangeRule(min=column.stats["min"], max=column.stats["max"])
        if column.inferred_type == "datetime" and {"min", "max"} <= set(column.stats):
            date_ranges[column.name] = DateRangeRule(min=column.stats["min"], max=column.stats["max"])

    pii_columns = sorted({column for issue in audit.issues if issue.category == "privacy" for column in issue.columns})
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


def _contract_type(inferred_type: str) -> str:
    return "text" if inferred_type == "empty" else inferred_type
