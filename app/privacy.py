from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s().-]{6,}$")
IP_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
CARD_RE = re.compile(r"^(?:\d[ -]*?){13,19}$")
NATIONAL_ID_RE = re.compile(r"^[A-Z0-9-]{6,20}$", re.I)


@dataclass(frozen=True)
class PrivacySignal:
    classification: str
    sensitivity: str
    confidence: float
    reasons: list[str]
    masking: str


NAME_TOKENS = {
    "email": ("email", "high", "Mask the local part or tokenize the full address."),
    "phone": ("phone_number", "high", "Mask all but the final four digits."),
    "mobile": ("phone_number", "high", "Mask all but the final four digits."),
    "first_name": ("person_name", "medium", "Use initials or pseudonymize before sharing."),
    "last_name": ("person_name", "medium", "Use initials or pseudonymize before sharing."),
    "full_name": ("person_name", "high", "Pseudonymize or tokenize names before sharing."),
    "name": ("person_name", "medium", "Pseudonymize or tokenize names before sharing."),
    "address": ("postal_address", "high", "Generalize or redact street-level details."),
    "passport": ("government_identifier", "critical", "Tokenize and restrict access."),
    "national_id": ("government_identifier", "critical", "Tokenize and restrict access."),
    "ssn": ("government_identifier", "critical", "Tokenize and restrict access."),
    "date_of_birth": ("date_of_birth", "high", "Generalize to age band where possible."),
    "dob": ("date_of_birth", "high", "Generalize to age band where possible."),
    "credit_card": ("payment_card", "critical", "Never expose raw card values; tokenize immediately."),
    "card_number": ("payment_card", "critical", "Never expose raw card values; tokenize immediately."),
    "bank_account": ("financial_account", "critical", "Tokenize and restrict access."),
    "account_number": ("financial_account", "high", "Mask and restrict access."),
    "ip_address": ("network_identifier", "medium", "Hash or truncate before analytics sharing."),
}

SENSITIVITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _clean_values(series: pd.Series, limit: int = 250) -> list[str]:
    values = series.dropna().astype(str).str.strip()
    values = values[values.ne("")].head(limit)
    return values.tolist()


def _luhn(value: str) -> bool:
    digits = [int(ch) for ch in re.sub(r"\D", "", value)]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def classify_sensitive_column(name: str, series: pd.Series) -> PrivacySignal | None:
    lowered = name.strip().lower().replace(" ", "_")
    values = _clean_values(series)
    metadata_tokens = ("verified", "verification", "valid", "is_", "has_", "consent", "opt_in", "flag", "status")
    boolean_values = {value.lower() for value in values}
    if "email" in lowered and (
        any(token in lowered for token in metadata_tokens)
        or pd.api.types.is_bool_dtype(series)
        or (boolean_values and boolean_values.issubset({"true", "false", "yes", "no", "y", "n", "1", "0"}))
    ):
        return None
    reasons: list[str] = []
    candidates: list[tuple[str, str, float, str]] = []

    for token, (classification, sensitivity, masking) in NAME_TOKENS.items():
        if token in lowered:
            candidates.append((classification, sensitivity, 0.93, masking))
            reasons.append(f"Column name contains '{token}'.")
            break

    if values:
        sample_size = len(values)
        date_like_name = any(token in lowered for token in ("date", "time", "created", "updated", "timestamp"))
        checks = {
            "email": sum(bool(EMAIL_RE.match(v)) for v in values) / sample_size,
            "phone_number": 0.0 if date_like_name else sum(bool(PHONE_RE.match(v)) for v in values) / sample_size,
            "network_identifier": sum(bool(IP_RE.match(v)) for v in values) / sample_size,
            "payment_card": 0.0
            if date_like_name
            else sum(bool(CARD_RE.match(v)) and _luhn(v) for v in values) / sample_size,
        }
        pattern_meta = {
            "email": ("high", "Mask the local part or tokenize the full address."),
            "phone_number": ("high", "Mask all but the final four digits."),
            "network_identifier": ("medium", "Hash or truncate before analytics sharing."),
            "payment_card": ("critical", "Never expose raw card values; tokenize immediately."),
        }
        for classification, ratio in checks.items():
            if ratio >= 0.6:
                sensitivity, masking = pattern_meta[classification]
                candidates.append((classification, sensitivity, min(0.99, 0.75 + ratio * 0.24), masking))
                reasons.append(f"{ratio:.0%} of sampled values match the {classification.replace('_', ' ')} pattern.")

        if any(token in lowered for token in ("id", "identifier", "number")):
            ratio = sum(bool(NATIONAL_ID_RE.match(v)) for v in values) / sample_size
            if ratio >= 0.8 and len(set(values)) / sample_size >= 0.8:
                candidates.append(("personal_identifier", "high", 0.84, "Tokenize or hash identifiers before sharing."))
                reasons.append("Values are mostly unique and identifier-like.")

    if not candidates:
        return None

    classification, sensitivity, confidence, masking = max(
        candidates, key=lambda item: (SENSITIVITY_ORDER[item[1]], item[2])
    )
    return PrivacySignal(
        classification=classification,
        sensitivity=sensitivity,
        confidence=round(confidence, 3),
        reasons=list(dict.fromkeys(reasons)),
        masking=masking,
    )


def scan_dataframe(frame: pd.DataFrame) -> dict:
    findings = []
    for column in frame.columns:
        signal = classify_sensitive_column(str(column), frame[column])
        if signal is None:
            continue
        findings.append(
            {
                "column": str(column),
                "classification": signal.classification,
                "sensitivity": signal.sensitivity,
                "confidence": signal.confidence,
                "reasons": signal.reasons,
                "masking_recommendation": signal.masking,
            }
        )
    counts = {level: sum(f["sensitivity"] == level for f in findings) for level in SENSITIVITY_ORDER}
    return {
        "sensitive_column_count": len(findings),
        "highest_sensitivity": max(
            (f["sensitivity"] for f in findings), key=lambda x: SENSITIVITY_ORDER[x], default="low"
        ),
        "counts": counts,
        "findings": findings,
    }
