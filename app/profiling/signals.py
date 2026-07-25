from __future__ import annotations


def cardinality_label(unique_count: int, row_count: int) -> str:
    if row_count == 0 or unique_count == 0:
        return "empty"
    rate = unique_count / row_count
    if unique_count == 1:
        return "constant"
    if rate <= 0.05:
        return "low"
    if rate >= 0.95:
        return "unique"
    if rate >= 0.5:
        return "high"
    return "medium"


def risk_assessment(*, missing_rate: float, outlier_rate: float, constant: bool, inferred_type: str) -> tuple[int, str, list[str]]:
    score = 0
    signals: list[str] = []
    if inferred_type == "empty":
        score += 70; signals.append("Column contains no usable values")
    if missing_rate >= 0.5:
        score += 45; signals.append("More than half of values are missing")
    elif missing_rate >= 0.1:
        score += 25; signals.append("Material missing-value rate")
    elif missing_rate > 0:
        score += 8; signals.append("Some values are missing")
    if outlier_rate >= 0.1:
        score += 30; signals.append("High numeric outlier rate")
    elif outlier_rate > 0:
        score += 12; signals.append("Numeric outliers detected")
    if constant:
        score += 20; signals.append("Column has one repeated value")
    score = min(score, 100)
    level = "high" if score >= 50 else "medium" if score >= 20 else "low"
    return score, level, signals
