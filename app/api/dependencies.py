from __future__ import annotations

from functools import lru_cache

from app.db.session import get_session_factory
from app.storage import AuditStore


@lru_cache
def get_audit_store() -> AuditStore:
    return AuditStore.from_session_factory(get_session_factory())
