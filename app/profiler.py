from __future__ import annotations

from typing import Any

import pandas as pd

from app.schemas import ColumnProfile, DatasetProfile


def infer_column_type(series: pd.Series) -> str:
    non_null = series.dropna()
    if non_null.empty:
        return "empty"
    column_name = str(series.name or "").lower()
    identifier_like_name = any(token in column_name for token in ("id", "phone", "mobile", "zip", "postal"))
    if identifier_like_name:
        return "text"
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    as_text = non_null.astype(str).str.strip()
    date_like_name = any(token in column_name for token in ("date", "time", "created", "updated", "timestamp"))
    text_contains_date_marker = as_text.str.contains(r"[-/]", regex=True).mean() >= 0.85
    if date_like_name or text_contains_date_marker:
        parsed_dates = pd.to_datetime(as_text, errors="coerce", utc=True)
        if parsed_dates.notna().mean() >= 0.85:
            return "datetime"

    parsed_numbers = pd.to_numeric(as_text.str.replace(",", "", regex=False), errors="coerce")
    if parsed_numbers.notna().mean() >= 0.9:
        return "numeric"
    return "text"


def _column_stats(series: pd.Series, inferred_type: str) -> dict[str, Any]:
    non_null = series.dropna()
    if non_null.empty:
        return {}

    if inferred_type == "numeric":
        numbers = pd.to_numeric(non_null.astype(str).str.replace(",", "", regex=False), errors="coerce").dropna()
        if numbers.empty:
            return {}
        return {
            "min": float(numbers.min()),
            "max": float(numbers.max()),
            "mean": float(numbers.mean()),
            "median": float(numbers.median()),
        }

    if inferred_type == "datetime":
        dates = pd.to_datetime(non_null, errors="coerce", utc=True).dropna()
        if dates.empty:
            return {}
        return {
            "min": dates.min().isoformat(),
            "max": dates.max().isoformat(),
        }

    top_values = non_null.astype(str).str.strip().value_counts().head(5)
    return {
        "top_values": [
            {"value": str(value), "count": int(count)}
            for value, count in top_values.items()
        ]
    }


def profile_dataset(frame: pd.DataFrame) -> DatasetProfile:
    row_count = int(len(frame))
    columns: list[ColumnProfile] = []

    for column in frame.columns:
        series = frame[column]
        missing_count = int(series.isna().sum() + series.astype(str).str.strip().eq("").sum())
        unique_count = int(series.nunique(dropna=True))
        inferred_type = infer_column_type(series)
        sample_values = [
            str(value)
            for value in series.dropna().astype(str).str.strip()
            if str(value).strip()
        ][:5]

        columns.append(
            ColumnProfile(
                name=str(column),
                inferred_type=inferred_type,
                missing_count=missing_count,
                missing_rate=round(missing_count / row_count, 4),
                unique_count=unique_count,
                unique_rate=round(unique_count / row_count, 4),
                sample_values=sample_values,
                stats=_column_stats(series, inferred_type),
            )
        )

    return DatasetProfile(
        row_count=row_count,
        column_count=len(frame.columns),
        duplicate_row_count=int(frame.duplicated().sum()),
        columns=columns,
    )
