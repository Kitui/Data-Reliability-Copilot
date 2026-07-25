from __future__ import annotations

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password, utcnow
from app.db.models import UserRecord
from app.db.session import session_scope


def ensure_bootstrap_admin() -> None:
    settings = get_settings()
    email = settings.bootstrap_admin_email.strip().lower()
    with session_scope() as db:
        existing = db.scalar(select(UserRecord).where(UserRecord.email == email))
        if existing:
            return
        db.add(UserRecord(
            email=email,
            full_name=settings.bootstrap_admin_name,
            password_hash=hash_password(settings.bootstrap_admin_password),
            role="admin",
            is_active=1,
            created_at=utcnow(),
        ))
