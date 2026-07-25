from __future__ import annotations

import pandas as pd


def infer_column_type(series: pd.Series) -> str:
    non_null = series.dropna()
    if non_null.empty:
        return "empty"
    name = str(series.name or "").lower()
    identifier_name = any(token in name for token in ("id", "phone", "mobile", "zip", "postal", "code"))
    if identifier_name:
        return "text"
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    text = non_null.astype(str).str.strip()
    bool_values = {"true", "false", "yes", "no", "y", "n", "0", "1"}
    if text.str.lower().isin(bool_values).mean() >= 0.95 and text.nunique() <= 6:
        return "boolean"

    date_name = any(token in name for token in ("date", "time", "created", "updated", "timestamp"))
    date_markers = text.str.contains(r"[-/:]", regex=True).mean() >= 0.8
    if date_name or date_markers:
        parsed = pd.to_datetime(text, errors="coerce", utc=True)
        if parsed.notna().mean() >= 0.85:
            return "datetime"

    numbers = pd.to_numeric(text.str.replace(",", "", regex=False), errors="coerce")
    if numbers.notna().mean() >= 0.9:
        return "numeric"
    return "text"
