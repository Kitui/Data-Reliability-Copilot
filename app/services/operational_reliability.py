from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.core.observability import metrics
from app.db.models import BackgroundJobRecord, OperationalAlertRecord
from app.db.session import get_engine, session_scope
from app.services.object_storage import GCSObjectStorage, LocalObjectStorage, build_object_storage


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def database_check() -> tuple[bool, str]:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:
        return False, type(exc).__name__


def storage_check() -> tuple[bool, str]:
    try:
        storage = build_object_storage()
        if isinstance(storage, LocalObjectStorage):
            probe = Path(storage.root) / ".drc-readiness"
            probe.write_bytes(b"ok")
            probe.unlink(missing_ok=True)
        elif isinstance(storage, GCSObjectStorage):
            # Verify the same object-level access DRC actually needs instead of
            # requesting bucket metadata. ``bucket.exists()`` requires the
            # broader ``storage.buckets.get`` permission, while listing a
            # single object works with the least-privilege object role used by
            # the application.
            iterator = storage.client.list_blobs(
                storage.bucket.name,
                max_results=1,
            )
            next(iter(iterator), None)
        return True, "ok"
    except Exception as exc:
        return False, type(exc).__name__


def queue_summary() -> dict[str, int]:
    with session_scope() as db:
        rows = db.execute(
            select(BackgroundJobRecord.status, func.count(BackgroundJobRecord.id)).group_by(BackgroundJobRecord.status)
        ).all()
    return {str(status): int(count) for status, count in rows}


def readiness_report() -> tuple[bool, dict]:
    db_ok, db_detail = database_check()
    storage_ok, storage_detail = storage_check()
    payload = {
        "database": {"status": "ok" if db_ok else "unavailable", "detail": db_detail},
        "storage": {"status": "ok" if storage_ok else "unavailable", "detail": storage_detail},
    }
    return db_ok and storage_ok, payload


def evaluate_operational_alerts() -> list[OperationalAlertRecord]:
    settings = get_settings()
    now = utcnow()
    created: list[OperationalAlertRecord] = []
    snapshot = metrics.snapshot()
    error_rate = snapshot.error_total / snapshot.request_total if snapshot.request_total else 0.0
    average_latency = snapshot.latency_sum_ms / snapshot.request_total if snapshot.request_total else 0.0
    queue = queue_summary()

    conditions = [
        ("http_error_rate", error_rate >= settings.ops_error_rate_threshold, "high", f"HTTP error rate is {error_rate:.2%}."),
        ("http_latency", average_latency >= settings.ops_latency_threshold_ms, "medium", f"Average HTTP latency is {average_latency:.0f} ms."),
        ("queue_depth", queue.get("queued", 0) >= settings.ops_queue_depth_threshold, "high", f"Queued job count is {queue.get('queued', 0)}."),
        ("failed_jobs", queue.get("failed", 0) >= settings.ops_failed_job_threshold, "high", f"Failed job count is {queue.get('failed', 0)}."),
    ]

    with session_scope() as db:
        for alert_type, active, severity, message in conditions:
            if not active:
                continue
            recent = db.scalar(select(OperationalAlertRecord).where(
                OperationalAlertRecord.alert_type == alert_type,
                OperationalAlertRecord.status == "open",
                OperationalAlertRecord.created_at >= now - timedelta(minutes=settings.ops_alert_cooldown_minutes),
            ))
            if recent:
                continue
            row = OperationalAlertRecord(
                alert_type=alert_type,
                severity=severity,
                status="open",
                message=message,
                details_json="{}",
                created_at=now,
                resolved_at=None,
            )
            db.add(row)
            db.flush()
            created.append(row)
    return created
