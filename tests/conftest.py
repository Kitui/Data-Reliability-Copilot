from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.api.dependencies import get_audit_store


@pytest.fixture(autouse=True)
def isolated_test_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Give every test a clean SQLite database and reset cached app resources."""
    database_path = tmp_path / "drc-test.db"
    monkeypatch.setenv("DRC_DATABASE_PATH", str(database_path))
    monkeypatch.delenv("DRC_DATABASE_URL", raising=False)
    monkeypatch.setenv("DRC_ENVIRONMENT", "testing")
    monkeypatch.setenv("DRC_STORAGE_BACKEND", "local")
    monkeypatch.setenv("DRC_CSRF_ENABLED", "false")
    monkeypatch.delenv("DRC_GCS_BUCKET", raising=False)
    monkeypatch.setenv("DRC_ADMIN_EMAIL", "admin@drc.local")
    monkeypatch.setenv("DRC_ADMIN_PASSWORD", "ChangeMe123!")
    monkeypatch.setenv("DRC_ENABLE_INTERNAL_SCHEDULER", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    get_settings.cache_clear()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    get_audit_store.cache_clear()

    yield

    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    get_audit_store.cache_clear()
    get_settings.cache_clear()
