from __future__ import annotations

from typing import Any

import pandas as pd


def numeric_values(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.dropna().astype(str).str.replace(",", "", regex=False), errors="coerce").dropna()


def outlier_summary(series: pd.Series, inferred_type: str) -> tuple[int, float]:
    if inferred_type != "numeric":
        return 0, 0.0
    values = numeric_values(series)
    if len(values) < 4:
        return 0, 0.0
    q1, q3 = values.quantile([0.25, 0.75])
    iqr = q3 - q1
    if iqr == 0:
        return 0, 0.0
    count = int(((values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)).sum())
    return count, round(count / len(values), 4)


def column_stats(series: pd.Series, inferred_type: str) -> dict[str, Any]:
    non_null = series.dropna()
    if non_null.empty:
        return {}
    if inferred_type == "numeric":
        values = numeric_values(series)
        if values.empty:
            return {}
        std_value = float(values.std(ddof=0)) if len(values) else 0.0
        if pd.isna(std_value):
            std_value = 0.0
        return {
            "min": float(values.min()),
            "max": float(values.max()),
            "mean": round(float(values.mean()), 4),
            "median": float(values.median()),
            "std_dev": round(std_value, 4),
        }
    if inferred_type == "datetime":
        values = pd.to_datetime(non_null, errors="coerce", utc=True).dropna()
        return {} if values.empty else {"min": values.min().isoformat(), "max": values.max().isoformat()}
    text = non_null.astype(str).str.strip()
    top = text.value_counts().head(5)
    lengths = text.str.len()
    return {
        "min_length": int(lengths.min()),
        "max_length": int(lengths.max()),
        "average_length": round(float(lengths.mean()), 2),
        "top_values": [{"value": str(value), "count": int(count)} for value, count in top.items()],
    }
