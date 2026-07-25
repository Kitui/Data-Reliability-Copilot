from datetime import datetime, timezone
from pathlib import Path

from app.api.routes.audits import _utc_datetime


def test_naive_sqlite_audit_time_is_canonical_utc():
    value = _utc_datetime(datetime(2026, 7, 24, 16, 19, 14))
    assert value.tzinfo is timezone.utc
    assert value.isoformat() == "2026-07-24T16:19:14+00:00"


def test_audit_selector_and_detail_use_same_formatter():
    js = Path("app/static/app.js").read_text()
    assert "formatDateTime(item.created_at)" in js
    assert "formatDateTime(audit.created_at)" in js
