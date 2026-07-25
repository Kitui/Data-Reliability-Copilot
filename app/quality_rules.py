from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.schemas import QualityIssue, RuleExecution, RuleDefinition

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def execute_quality_rules(frame: pd.DataFrame, rules: list[RuleDefinition], starting_index: int = 1) -> tuple[list[QualityIssue], list[RuleExecution]]:
    issues: list[QualityIssue] = []
    executions: list[RuleExecution] = []
    row_count = max(len(frame), 1)

    for offset, rule in enumerate(rules, start=starting_index):
        started = datetime.now(timezone.utc)
        issue_id = f"QR-{offset:03d}"
        affected_mask, message = _evaluate_rule(frame, rule)
        affected_rows = int(affected_mask.sum()) if affected_mask is not None else 0
        outcome = "failed" if affected_rows else "passed"
        affected_rate = round(affected_rows / row_count, 4)
        executions.append(RuleExecution(
            rule_id=rule.id,
            rule_name=rule.name,
            rule_type=rule.rule_type,
            outcome=outcome,
            affected_rows=affected_rows,
            affected_rate=affected_rate,
            message=message,
            executed_at=started,
        ))
        if affected_rows:
            columns = [rule.column_name] if rule.column_name else list(frame.columns)
            examples = frame.loc[affected_mask, columns].head(3).fillna("").to_dict(orient="records") if affected_mask is not None else []
            issues.append(QualityIssue(
                id=issue_id,
                category=rule.category,
                severity=rule.severity,
                title=f"{rule.name} failed",
                detail=message,
                columns=columns,
                affected_rows=affected_rows,
                affected_rate=affected_rate,
                examples=examples,
                recommendation=rule.recommendation or _default_recommendation(rule),
                confidence=1.0,
                rule_id=rule.id,
                rule_name=rule.name,
            ))
    return issues, executions


def _evaluate_rule(frame: pd.DataFrame, rule: RuleDefinition) -> tuple[pd.Series | None, str]:
    params = rule.parameters
    column = rule.column_name
    if rule.rule_type == "duplicate_rows":
        mask = frame.duplicated(keep=False)
        return mask, f"{int(mask.sum())} duplicated rows were detected."

    if not column or column not in frame.columns:
        mask = pd.Series([True] * len(frame), index=frame.index)
        return mask, f"Configured column '{column or ''}' is missing from the dataset."

    series = frame[column]
    text = series.astype(str).str.strip()
    missing = series.isna() | text.eq("")

    if rule.rule_type == "required":
        return missing, f"{int(missing.sum())} rows are missing a required value in {column}."
    if rule.rule_type == "unique":
        mask = ~missing & text.duplicated(keep=False)
        return mask, f"{int(mask.sum())} rows contain duplicate values in {column}."
    if rule.rule_type == "email":
        mask = ~missing & ~text.map(lambda value: bool(EMAIL_PATTERN.match(value)))
        return mask, f"{int(mask.sum())} rows contain invalid email values in {column}."
    if rule.rule_type == "allowed_values":
        allowed = {str(value) for value in params.get("values", [])}
        mask = ~missing & ~text.isin(allowed)
        return mask, f"{int(mask.sum())} rows contain values outside the configured allowed set in {column}."
    if rule.rule_type == "regex":
        pattern = re.compile(str(params.get("pattern", ".*")))
        mask = ~missing & ~text.map(lambda value: bool(pattern.fullmatch(value)))
        return mask, f"{int(mask.sum())} rows do not match the configured pattern in {column}."
    if rule.rule_type == "numeric_range":
        numeric = pd.to_numeric(series, errors="coerce")
        mask = ~missing & numeric.isna()
        if params.get("min") is not None:
            mask = mask | numeric.lt(float(params["min"]))
        if params.get("max") is not None:
            mask = mask | numeric.gt(float(params["max"]))
        return mask.fillna(False), f"{int(mask.fillna(False).sum())} rows fall outside the configured numeric range in {column}."
    if rule.rule_type == "length_range":
        lengths = text.str.len()
        mask = pd.Series(False, index=frame.index)
        if params.get("min") is not None:
            mask = mask | (~missing & lengths.lt(int(params["min"])))
        if params.get("max") is not None:
            mask = mask | (~missing & lengths.gt(int(params["max"])))
        return mask, f"{int(mask.sum())} rows fall outside the configured length range in {column}."
    if rule.rule_type == "missing_threshold":
        threshold = float(params.get("max_rate", 0))
        if float(missing.mean()) <= threshold:
            return pd.Series(False, index=frame.index), f"Missing rate is within the configured {threshold:.0%} threshold."
        return missing, f"Missing rate {float(missing.mean()):.2%} exceeds the configured {threshold:.2%} threshold in {column}."
    if rule.rule_type == "expected_type":
        expected = str(params.get("type", "text"))
        if expected == "numeric":
            parsed = pd.to_numeric(series, errors="coerce")
        elif expected == "datetime":
            parsed = pd.to_datetime(series, errors="coerce")
        elif expected == "boolean":
            parsed = text.str.lower().where(text.str.lower().isin({"true", "false", "yes", "no", "1", "0"}))
        else:
            return pd.Series(False, index=frame.index), "Text values satisfy the configured type."
        mask = ~missing & parsed.isna()
        return mask, f"{int(mask.sum())} rows do not match the expected {expected} type in {column}."
    if rule.rule_type == "stale_days":
        dates = pd.to_datetime(series, errors="coerce", utc=True)
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=int(params.get("days", 30)))
        mask = ~missing & (dates.isna() | dates.lt(cutoff))
        return mask, f"{int(mask.sum())} rows are older than the configured freshness window in {column}."

    return pd.Series(False, index=frame.index), "Rule type is not currently evaluated."


def _default_recommendation(rule: RuleDefinition) -> str:
    recommendations = {
        "required": "Fill or reject records with missing required values.",
        "unique": "Deduplicate the column using the correct business key.",
        "email": "Standardize email capture and reject invalid addresses.",
        "allowed_values": "Map unexpected labels to the approved value set.",
        "regex": "Correct values that do not match the required pattern.",
        "numeric_range": "Review and correct values outside the approved numeric range.",
        "length_range": "Normalize values to the configured length constraints.",
        "missing_threshold": "Backfill missing values or revise the threshold with governance approval.",
        "expected_type": "Correct source formatting or update the expected schema type.",
        "stale_days": "Refresh stale records from the source system.",
        "duplicate_rows": "Remove duplicated rows using a stable record key.",
    }
    return recommendations.get(rule.rule_type, "Review and correct the records that failed this rule.")
