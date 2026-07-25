from __future__ import annotations

import re

from app.core.config import get_settings


def validate_password(password: str) -> list[str]:
    minimum = get_settings().password_min_length
    errors: list[str] = []
    if len(password) < minimum:
        errors.append(f"Password must contain at least {minimum} characters.")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must include an uppercase letter.")
    if not re.search(r"[a-z]", password):
        errors.append("Password must include a lowercase letter.")
    if not re.search(r"\d", password):
        errors.append("Password must include a number.")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("Password must include a special character.")
    return errors
