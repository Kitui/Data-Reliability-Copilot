from __future__ import annotations

import re
from itertools import count
from typing import Any

import pandas as pd

from app.schemas import AuditRuleConfig, DatasetProfile, QualityIssue, Severity


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9\s().-]{6,}$")
NATIONAL_ID_PATTERN = re.compile(r"^\d{6,12}$")


def detect_issues(
    frame: pd.DataFrame,
    profile: DatasetProfile,
    config: AuditRuleConfig | None = None,
) -> list[QualityIssue]:
    config = config or AuditRuleConfig()
    issue_ids = count(1)
    issues: list[QualityIssue] = []
    row_count = max(profile.row_count, 1)

    def add_issue(
        category: str,
        severity: Severity,
        title: str,
        detail: str,
        columns: list[str],
        affected_rows: int,
        recommendation: str,
        confidence: float,
        examples: list[dict[str, Any]] | None = None,
    ) -> None:
        issues.append(
            QualityIssue(
                id=f"DQ-{next(issue_ids):03d}",
                category=category,  # type: ignore[arg-type]
                severity=severity,
                title=title,
                detail=detail,
                columns=columns,
                affected_rows=affected_rows,
                affected_rate=round(affected_rows / row_count, 4),
                examples=examples or [],
                recommendation=recommendation,
                confidence=confidence,
            )
        )

    for column in profile.columns:
        if column.missing_rate >= 0.5:
            severity: Severity = "critical"
        elif column.missing_rate >= 0.2:
            severity = "high"
        elif column.missing_rate >= 0.05:
            severity = "medium"
        else:
            severity = "low"

        if column.missing_count:
            add_issue(
                "completeness",
                severity,
                f"Missing values in {column.name}",
                f"{column.missing_count} rows are blank or null in this column.",
                [column.name],
                column.missing_count,
                "Confirm whether the field is required, then fill, backfill, or exclude incomplete records.",
                0.98,
                _examples(frame, [column.name], frame[column.name].isna() | frame[column.name].astype(str).str.strip().eq("")),
            )

        if column.unique_count == 1 and profile.row_count > 1:
            add_issue(
                "consistency",
                "medium",
                f"{column.name} has one repeated value",
                "This column is constant across the dataset and may not add analytical value.",
                [column.name],
                profile.row_count,
                "Confirm whether this column is expected to be constant; otherwise review extraction or mapping logic.",
                0.9,
            )

    if profile.duplicate_row_count:
        add_issue(
            "uniqueness",
            "high" if profile.duplicate_row_count / row_count >= 0.05 else "medium",
            "Duplicate rows detected",
            f"{profile.duplicate_row_count} complete rows are duplicated.",
            list(frame.columns),
            profile.duplicate_row_count,
            "Deduplicate records using a stable business key before reporting or model training.",
            0.99,
            _examples(frame, list(frame.columns), frame.duplicated(keep=False)),
        )

    _detect_key_duplicates(frame, add_issue)
    _detect_email_issues(frame, add_issue)
    _detect_phone_issues(frame, add_issue)
    _detect_pii_columns(frame, add_issue)
    _detect_numeric_outliers(frame, add_issue)
    _detect_numeric_business_rules(frame, add_issue)
    _detect_date_quality(frame, add_issue)
    _detect_cross_field_dates(frame, add_issue)
    _detect_contact_integrity(frame, add_issue)
    _detect_mixed_categories(frame, add_issue)
    _detect_configured_rules(frame, profile, config, add_issue)

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(issues, key=lambda issue: (severity_order[issue.severity], issue.id))


def _examples(frame: pd.DataFrame, columns: list[str], mask: pd.Series, limit: int = 3) -> list[dict[str, Any]]:
    selected = frame.loc[mask, columns].head(limit)
    return selected.fillna("").to_dict(orient="records")


def _detect_email_issues(frame: pd.DataFrame, add_issue) -> None:
    for column in frame.columns:
        if "email" not in str(column).lower():
            continue
        values = frame[column].dropna().astype(str).str.strip()
        invalid = values.ne("") & ~values.map(lambda value: bool(EMAIL_PATTERN.match(value)))
        if invalid.any():
            mask = frame[column].astype(str).str.strip().isin(values[invalid])
            add_issue(
                "validity",
                "high",
                f"Invalid email format in {column}",
                "Some values do not match a standard email pattern.",
                [str(column)],
                int(invalid.sum()),
                "Standardize email capture and reject addresses that do not contain a valid local part and domain.",
                0.96,
                _examples(frame, [str(column)], mask),
            )


def _detect_key_duplicates(frame: pd.DataFrame, add_issue) -> None:
    for column in frame.columns:
        lowered = str(column).lower()
        if not any(token in lowered for token in ("id", "key", "number", "code")):
            continue
        values = frame[column].dropna().astype(str).str.strip()
        if values.empty:
            continue
        duplicated = values.ne("") & values.duplicated(keep=False)
        if duplicated.any():
            mask = frame[column].astype(str).str.strip().isin(values[duplicated])
            affected = int(mask.sum())
            add_issue(
                "uniqueness",
                "high",
                f"Duplicate key values in {column}",
                "A likely business key contains repeated values.",
                [str(column)],
                affected,
                "Confirm the correct primary key and deduplicate records at the business-entity level.",
                0.94,
                _examples(frame, [str(column)], mask),
            )


def _detect_phone_issues(frame: pd.DataFrame, add_issue) -> None:
    for column in frame.columns:
        lowered = str(column).lower()
        if "phone" not in lowered and "mobile" not in lowered:
            continue
        values = frame[column].dropna().astype(str).str.strip()
        invalid = values.ne("") & ~values.map(lambda value: bool(PHONE_PATTERN.match(value)))
        if invalid.any():
            mask = frame[column].astype(str).str.strip().isin(values[invalid])
            add_issue(
                "validity",
                "medium",
                f"Invalid phone format in {column}",
                "Some values do not look like reachable phone numbers.",
                [str(column)],
                int(invalid.sum()),
                "Normalize phone numbers into a single international or local format.",
                0.88,
                _examples(frame, [str(column)], mask),
            )


def _detect_pii_columns(frame: pd.DataFrame, add_issue) -> None:
    pii_columns: list[str] = []
    for column in frame.columns:
        lowered = str(column).lower()
        values = frame[column].dropna().astype(str).str.strip()
        sample = values.head(100)
        if any(token in lowered for token in ("email", "phone", "mobile", "name", "address", "national_id", "passport")):
            pii_columns.append(str(column))
        elif sample.map(lambda value: bool(EMAIL_PATTERN.match(value))).mean() >= 0.6:
            pii_columns.append(str(column))
        elif any(token in lowered for token in ("date", "time", "created", "updated")):
            continue
        elif sample.map(lambda value: bool(PHONE_PATTERN.match(value))).mean() >= 0.6:
            pii_columns.append(str(column))
        elif "id" in lowered and sample.map(lambda value: bool(NATIONAL_ID_PATTERN.match(value))).mean() >= 0.6:
            pii_columns.append(str(column))

    if pii_columns:
        add_issue(
            "privacy",
            "medium",
            "Potential PII columns detected",
            "The dataset appears to contain personal or contact information.",
            pii_columns,
            len(frame),
            "Apply access controls, avoid sending raw values to LLMs, and mask or hash sensitive fields before sharing.",
            0.86,
        )


def _detect_numeric_outliers(frame: pd.DataFrame, add_issue) -> None:
    for column in frame.columns:
        lowered = str(column).lower()
        if any(token in lowered for token in ("id", "phone", "mobile", "zip", "postal")):
            continue
        numbers = pd.to_numeric(frame[column], errors="coerce")
        if numbers.notna().sum() < 8:
            continue
        q1 = numbers.quantile(0.25)
        q3 = numbers.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        mask = numbers.lt(lower) | numbers.gt(upper)
        if mask.any():
            add_issue(
                "anomaly",
                "medium",
                f"Outliers detected in {column}",
                f"Values outside the expected range of {lower:.2f} to {upper:.2f} were found.",
                [str(column)],
                int(mask.sum()),
                "Review outliers against source records before excluding or capping them.",
                0.82,
                _examples(frame, [str(column)], mask),
            )


def _detect_numeric_business_rules(frame: pd.DataFrame, add_issue) -> None:
    for column in frame.columns:
        lowered = str(column).lower()
        numbers = pd.to_numeric(frame[column], errors="coerce")
        if numbers.notna().sum() == 0:
            continue

        if any(token in lowered for token in ("price", "amount", "spend", "cost", "revenue", "salary", "balance")):
            mask = numbers.lt(0)
            if mask.any():
                add_issue(
                    "validity",
                    "high",
                    f"Negative monetary values in {column}",
                    "A money-like field contains values below zero.",
                    [str(column)],
                    int(mask.sum()),
                    "Confirm whether negative values are valid adjustments; otherwise correct source transactions.",
                    0.9,
                    _examples(frame, [str(column)], mask),
                )

        if any(token in lowered for token in ("percent", "percentage", "rate", "ratio")):
            mask = numbers.lt(0) | numbers.gt(100)
            if mask.any():
                add_issue(
                    "validity",
                    "medium",
                    f"Percentage values outside 0-100 in {column}",
                    "A percentage-like field contains values outside the expected range.",
                    [str(column)],
                    int(mask.sum()),
                    "Normalize percentages to a consistent 0-100 or 0-1 convention.",
                    0.87,
                    _examples(frame, [str(column)], mask),
                )

        if "age" in lowered:
            mask = numbers.lt(0) | numbers.gt(120)
            if mask.any():
                add_issue(
                    "validity",
                    "high",
                    f"Impossible age values in {column}",
                    "Age values should normally fall between 0 and 120.",
                    [str(column)],
                    int(mask.sum()),
                    "Validate date-of-birth or age calculation logic at ingestion.",
                    0.91,
                    _examples(frame, [str(column)], mask),
                )


def _detect_date_quality(frame: pd.DataFrame, add_issue) -> None:
    now = pd.Timestamp.utcnow()
    for column in frame.columns:
        lowered = str(column).lower()
        if not any(token in lowered for token in ("date", "time", "created", "updated", "dob", "birth")):
            continue
        dates = pd.to_datetime(frame[column], errors="coerce", utc=True)
        valid_dates = dates.dropna()
        if valid_dates.empty:
            continue

        future_mask = dates.gt(now)
        if future_mask.any():
            add_issue(
                "validity",
                "medium",
                f"Future dates in {column}",
                "Some records contain dates later than today.",
                [str(column)],
                int(future_mask.sum()),
                "Verify whether future dates are expected; otherwise correct timezone, parsing, or source-entry errors.",
                0.88,
                _examples(frame, [str(column)], future_mask),
            )

        if any(token in lowered for token in ("dob", "birth")):
            too_old = dates.lt(now - pd.DateOffset(years=120))
            too_young = dates.gt(now)
            mask = too_old | too_young
            if mask.any():
                add_issue(
                    "validity",
                    "high",
                    f"Impossible birth dates in {column}",
                    "Birth-date values imply impossible ages.",
                    [str(column)],
                    int(mask.sum()),
                    "Validate birth dates and confirm date formats before using age-derived features.",
                    0.9,
                    _examples(frame, [str(column)], mask),
                )

        stale_cutoff = now - pd.DateOffset(years=3)
        if any(token in lowered for token in ("updated", "last_seen", "last_login", "modified")):
            stale_mask = dates.lt(stale_cutoff)
            if stale_mask.any():
                add_issue(
                "timeliness",
                    "medium",
                    f"Stale timestamp values in {column}",
                    "Some records have not been updated in more than three years.",
                    [str(column)],
                    int(stale_mask.sum()),
                    "Refresh stale records or exclude them from current-state reporting.",
                    0.82,
                    _examples(frame, [str(column)], stale_mask),
                )


def _detect_cross_field_dates(frame: pd.DataFrame, add_issue) -> None:
    lower_to_column = {str(column).lower(): column for column in frame.columns}
    date_pairs = [
        ("start_date", "end_date"),
        ("created_at", "updated_at"),
        ("signup_date", "cancelled_date"),
    ]
    for start_name, end_name in date_pairs:
        if start_name not in lower_to_column or end_name not in lower_to_column:
            continue
        start_column = lower_to_column[start_name]
        end_column = lower_to_column[end_name]
        start_dates = pd.to_datetime(frame[start_column], errors="coerce", utc=True)
        end_dates = pd.to_datetime(frame[end_column], errors="coerce", utc=True)
        mask = start_dates.notna() & end_dates.notna() & end_dates.lt(start_dates)
        if mask.any():
            add_issue(
                "integrity",
                "high",
                f"{end_column} is before {start_column}",
                "A date relationship is logically inconsistent.",
                [str(start_column), str(end_column)],
                int(mask.sum()),
                "Correct date ordering before lifecycle, retention, or duration analysis.",
                0.93,
                _examples(frame, [str(start_column), str(end_column)], mask),
            )


def _detect_contact_integrity(frame: pd.DataFrame, add_issue) -> None:
    columns = {str(column).lower(): column for column in frame.columns}
    status_column = columns.get("status")
    email_column = columns.get("email")
    phone_column = columns.get("phone") or columns.get("mobile")
    if status_column is None or (email_column is None and phone_column is None):
        return

    status = frame[status_column].astype(str).str.strip().str.lower()
    active = status.eq("active")
    masks = []
    contact_columns: list[str] = []
    if email_column is not None:
        masks.append(frame[email_column].isna() | frame[email_column].astype(str).str.strip().eq(""))
        contact_columns.append(str(email_column))
    if phone_column is not None:
        masks.append(frame[phone_column].isna() | frame[phone_column].astype(str).str.strip().eq(""))
        contact_columns.append(str(phone_column))
    missing_contact = masks[0]
    for mask in masks[1:]:
        missing_contact = missing_contact & mask
    issue_mask = active & missing_contact
    if issue_mask.any():
        add_issue(
            "integrity",
            "high",
            "Active records missing contact details",
            "Some active entities do not have usable contact information.",
            [str(status_column), *contact_columns],
            int(issue_mask.sum()),
            "Require at least one contact channel for active records.",
            0.9,
            _examples(frame, [str(status_column), *contact_columns], issue_mask),
        )


def _detect_mixed_categories(frame: pd.DataFrame, add_issue) -> None:
    for column in frame.columns:
        values = frame[column].dropna().astype(str).str.strip()
        if values.empty or values.nunique() > 50:
            continue
        normalized = values.str.lower()
        if normalized.nunique() < values.nunique():
            affected = int(values.nunique() - normalized.nunique())
            add_issue(
                "consistency",
                "low",
                f"Inconsistent category casing in {column}",
                "Some category labels only differ by capitalization or surrounding spaces.",
                [str(column)],
                affected,
                "Normalize category labels before aggregating or training models.",
                0.84,
            )


def _detect_configured_rules(
    frame: pd.DataFrame,
    profile: DatasetProfile,
    config: AuditRuleConfig,
    add_issue,
) -> None:
    columns = {str(column): column for column in frame.columns}
    lower_columns = {str(column).lower(): column for column in frame.columns}

    for required in config.required_columns:
        if required not in columns and required.lower() not in lower_columns:
            add_issue(
                "schema",
                "critical",
                f"Required column missing: {required}",
                "The dataset does not include a configured required column.",
                [required],
                profile.row_count,
                "Update the export or mapping so the required column is present before auditing downstream quality.",
                0.99,
            )

    for configured_column in config.unique_columns:
        column = columns.get(configured_column) or lower_columns.get(configured_column.lower())
        if column is None:
            continue
        values = frame[column].dropna().astype(str).str.strip()
        duplicated = values.ne("") & values.duplicated(keep=False)
        if duplicated.any():
            mask = frame[column].astype(str).str.strip().isin(values[duplicated])
            add_issue(
                "uniqueness",
                "critical",
                f"Configured unique column has duplicates: {column}",
                "A user-configured unique field contains repeated values.",
                [str(column)],
                int(mask.sum()),
                "Deduplicate or correct this field before using it as a key.",
                0.98,
                _examples(frame, [str(column)], mask),
            )

    for configured_column, expected_type in config.expected_types.items():
        profile_column = next((column for column in profile.columns if column.name.lower() == configured_column.lower()), None)
        if profile_column and profile_column.inferred_type != expected_type:
            add_issue(
                "schema",
                "high",
                f"Unexpected type for {profile_column.name}",
                f"Configured type is {expected_type}, but the profiler inferred {profile_column.inferred_type}.",
                [profile_column.name],
                profile.row_count,
                "Review source formatting or update the configured schema if the type has intentionally changed.",
                0.89,
            )

    for configured_column, allowed in config.allowed_values.items():
        column = columns.get(configured_column) or lower_columns.get(configured_column.lower())
        if column is None:
            continue
        allowed_normalized = {value.strip() for value in allowed}
        values = frame[column].dropna().astype(str).str.strip()
        invalid = values.ne("") & ~values.isin(allowed_normalized)
        if invalid.any():
            mask = frame[column].astype(str).str.strip().isin(values[invalid])
            add_issue(
                "validity",
                "high",
                f"Values outside allowed set in {column}",
                "A configured categorical field contains unexpected labels.",
                [str(column)],
                int(mask.sum()),
                "Map unexpected values to the approved vocabulary or fix source-entry validation.",
                0.95,
                _examples(frame, [str(column)], mask),
            )

    for configured_column, bounds in config.numeric_ranges.items():
        column = columns.get(configured_column) or lower_columns.get(configured_column.lower())
        if column is None:
            continue
        numbers = pd.to_numeric(frame[column], errors="coerce")
        mask = pd.Series(False, index=frame.index)
        if bounds.min is not None:
            mask = mask | numbers.lt(bounds.min)
        if bounds.max is not None:
            mask = mask | numbers.gt(bounds.max)
        if mask.any():
            add_issue(
                "validity",
                "high",
                f"Configured numeric range violated in {column}",
                "A numeric field contains values outside configured limits.",
                [str(column)],
                int(mask.sum()),
                "Correct out-of-range values or revise the configured bounds.",
                0.94,
                _examples(frame, [str(column)], mask),
            )

    now = pd.Timestamp.utcnow()
    for configured_column, bounds in config.date_ranges.items():
        column = columns.get(configured_column) or lower_columns.get(configured_column.lower())
        if column is None:
            continue
        dates = pd.to_datetime(frame[column], errors="coerce", utc=True)
        mask = pd.Series(False, index=frame.index)
        if bounds.min is not None:
            mask = mask | dates.lt(pd.Timestamp(bounds.min, tz="UTC"))
        if bounds.max is not None:
            max_date = now if bounds.max.lower() == "today" else pd.Timestamp(bounds.max, tz="UTC")
            mask = mask | dates.gt(max_date)
        if mask.any():
            add_issue(
                "validity",
                "high",
                f"Configured date range violated in {column}",
                "A date field contains values outside configured limits.",
                [str(column)],
                int(mask.sum()),
                "Correct date values or adjust the configured date range.",
                0.94,
                _examples(frame, [str(column)], mask),
            )

    for configured_column, days in config.stale_after_days.items():
        column = columns.get(configured_column) or lower_columns.get(configured_column.lower())
        if column is None:
            continue
        dates = pd.to_datetime(frame[column], errors="coerce", utc=True)
        mask = dates.lt(now - pd.Timedelta(days=days))
        if mask.any():
            add_issue(
                "validity",
                "medium",
                f"Configured staleness threshold exceeded in {column}",
                f"Some records are older than the configured {days}-day freshness window.",
                [str(column)],
                int(mask.sum()),
                "Refresh stale records or exclude them from current-state reporting.",
                0.88,
                _examples(frame, [str(column)], mask),
            )
