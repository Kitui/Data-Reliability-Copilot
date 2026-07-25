from __future__ import annotations

import pandas as pd

from app.privacy import SENSITIVITY_ORDER, classify_sensitive_column
from app.profiling.inference import infer_column_type
from app.profiling.signals import cardinality_label, risk_assessment
from app.profiling.statistics import column_stats, outlier_summary
from app.schemas import ColumnProfile, DatasetProfile


def _missing_mask(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype(str).str.strip().eq("")


def profile_dataset(frame: pd.DataFrame) -> DatasetProfile:
    row_count = int(len(frame))
    columns: list[ColumnProfile] = []
    total_cells = max(row_count * len(frame.columns), 1)
    total_missing = 0

    for column in frame.columns:
        series = frame[column]
        missing_count = int(_missing_mask(series).sum())
        total_missing += missing_count
        unique_count = int(series[~_missing_mask(series)].nunique(dropna=True))
        missing_rate = round(missing_count / row_count, 4) if row_count else 0.0
        unique_rate = round(unique_count / row_count, 4) if row_count else 0.0
        inferred_type = infer_column_type(series)
        outlier_count, outlier_rate = outlier_summary(series, inferred_type)
        cardinality = cardinality_label(unique_count, row_count)
        constant = unique_count == 1 and row_count > 1
        name = str(column)
        identifier_candidate = unique_rate >= 0.95 or any(token in name.lower() for token in ("id", "key", "uuid"))
        risk_score, risk_level, signals = risk_assessment(
            missing_rate=missing_rate,
            outlier_rate=outlier_rate,
            constant=constant,
            inferred_type=inferred_type,
        )
        privacy = classify_sensitive_column(name, series)
        samples = [str(value) for value in series.dropna().astype(str).str.strip() if str(value).strip()][:5]
        columns.append(
            ColumnProfile(
                name=name,
                inferred_type=inferred_type,
                missing_count=missing_count,
                missing_rate=missing_rate,
                unique_count=unique_count,
                unique_rate=unique_rate,
                sample_values=samples,
                stats=column_stats(series, inferred_type),
                cardinality=cardinality,
                constant=constant,
                identifier_candidate=identifier_candidate,
                outlier_count=outlier_count,
                outlier_rate=outlier_rate,
                risk_score=risk_score,
                risk_level=risk_level,
                signals=signals,
                privacy_classification=privacy.classification if privacy else None,
                sensitivity=privacy.sensitivity if privacy else None,
                privacy_confidence=privacy.confidence if privacy else 0.0,
                privacy_reasons=privacy.reasons if privacy else [],
                masking_recommendation=privacy.masking if privacy else None,
            )
        )

    duplicate_count = int(frame.duplicated().sum())
    sensitive = [c for c in columns if c.sensitivity]
    highest = max((c.sensitivity for c in sensitive), key=lambda x: SENSITIVITY_ORDER[x], default="low")
    return DatasetProfile(
        row_count=row_count,
        column_count=len(frame.columns),
        duplicate_row_count=duplicate_count,
        completeness_rate=round(1 - total_missing / total_cells, 4),
        duplicate_row_rate=round(duplicate_count / row_count, 4) if row_count else 0.0,
        high_risk_column_count=sum(c.risk_level == "high" for c in columns),
        medium_risk_column_count=sum(c.risk_level == "medium" for c in columns),
        sensitive_column_count=len(sensitive),
        highest_sensitivity=highest,
        columns=columns,
    )
