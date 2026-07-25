from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select

from app.api.auth_dependencies import require_roles
from app.core.config import get_settings
from app.core.observability import metrics
from app.db.models import OperationalAlertRecord
from app.db.session import session_scope
from app.services.operational_reliability import database_check, evaluate_operational_alerts, queue_summary, readiness_report

router = APIRouter(tags=["System"])


@router.get("/health")
@router.get("/health/live")
def liveness() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
def readiness(response: Response) -> dict:
    settings = get_settings()
    ready, checks = readiness_report()
    response.status_code = 200 if ready else 503
    return {
        "status": "ready" if ready else "not_ready",
        "service": settings.service_name,
        "version": settings.app_version,
        "checks": checks,
    }


@router.get("/metrics", response_class=Response)
def prometheus_metrics(x_drc_metrics_token: str | None = Header(default=None)) -> Response:
    settings = get_settings()
    if settings.metrics_token and x_drc_metrics_token != settings.metrics_token:
        raise HTTPException(status_code=403, detail="Invalid metrics token.")
    return Response(content=metrics.prometheus(), media_type="text/plain; version=0.0.4")


@router.get("/operations/summary")
def operations_summary(user: dict = Depends(require_roles("owner", "admin"))) -> dict:
    snapshot = metrics.snapshot()
    db_ok, db_detail = database_check()
    return {
        "database": {"available": db_ok, "detail": db_detail},
        "queue": queue_summary(),
        "http": {
            "requests": snapshot.request_total,
            "errors": snapshot.error_total,
            "active": snapshot.active_requests,
            "average_latency_ms": round(snapshot.latency_sum_ms / snapshot.request_total, 2) if snapshot.request_total else 0,
            "status_counts": snapshot.status_counts,
        },
    }


@router.post("/operations/alerts/evaluate")
def evaluate_alerts(user: dict = Depends(require_roles("owner", "admin"))) -> dict:
    created = evaluate_operational_alerts()
    return {"created": len(created), "alert_ids": [row.id for row in created]}


@router.get("/operations/alerts")
def list_operational_alerts(user: dict = Depends(require_roles("owner", "admin"))) -> list[dict]:
    with session_scope() as db:
        rows = db.scalars(select(OperationalAlertRecord).order_by(OperationalAlertRecord.created_at.desc()).limit(100)).all()
        return [{
            "id": row.id,
            "alert_type": row.alert_type,
            "severity": row.severity,
            "status": row.status,
            "message": row.message,
            "created_at": row.created_at,
            "resolved_at": row.resolved_at,
        } for row in rows]
