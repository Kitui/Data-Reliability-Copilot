from __future__ import annotations

import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.auth_dependencies import require_roles
from app.db.models import AdministrativeAuditLogRecord
from app.db.session import get_session_factory

router = APIRouter(prefix="/security", tags=["Security"])


@router.get("/audit-log")
def audit_log(
    limit: int = Query(default=100, ge=1, le=500),
    action: str | None = None,
    user: dict[str, object] = Depends(require_roles("owner", "admin")),
) -> list[dict[str, object]]:
    workspace_id = user["workspace"]["id"]
    Session = get_session_factory()
    with Session() as db:
        query = select(AdministrativeAuditLogRecord).where(AdministrativeAuditLogRecord.workspace_id == workspace_id)
        if action:
            query = query.where(AdministrativeAuditLogRecord.action == action)
        rows = db.scalars(query.order_by(AdministrativeAuditLogRecord.created_at.desc()).limit(limit)).all()
        return [{
            "id": row.id,
            "action": row.action,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "outcome": row.outcome,
            "actor_user_id": row.actor_user_id,
            "ip_address": row.ip_address,
            "details": json.loads(row.details_json or "{}"),
            "created_at": row.created_at,
        } for row in rows]
