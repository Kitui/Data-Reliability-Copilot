from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from sqlalchemy import select

from app.core.security import utcnow
from app.db.models import AdministrativeAuditLogRecord
from app.db.session import get_session_factory

SENSITIVE_KEYS = {"password", "token", "secret", "credential", "authorization", "cookie"}


def _safe_details(details: dict[str, Any] | None) -> str:
    clean: dict[str, Any] = {}
    for key, value in (details or {}).items():
        clean[key] = "[REDACTED]" if any(part in key.lower() for part in SENSITIVE_KEYS) else value
    return json.dumps(clean, default=str)


def record_security_event(
    action: str,
    *,
    request: Request | None = None,
    user: dict[str, object] | None = None,
    actor_user_id: int | None = None,
    organization_id: int | None = None,
    workspace_id: int | None = None,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    outcome: str = "success",
    details: dict[str, Any] | None = None,
) -> None:
    if user:
        actor_user_id = int(user["id"]) if user.get("id") is not None else actor_user_id
        org = user.get("organization") or {}
        ws = user.get("workspace") or {}
        organization_id = int(org["id"]) if isinstance(org, dict) and org.get("id") else organization_id
        workspace_id = int(ws["id"]) if isinstance(ws, dict) and ws.get("id") else workspace_id
    Session = get_session_factory()
    try:
        with Session() as db:
            db.add(
                AdministrativeAuditLogRecord(
                    workspace_id=workspace_id,
                    organization_id=organization_id,
                    actor_user_id=actor_user_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id is not None else None,
                    outcome=outcome,
                    ip_address=request.client.host if request and request.client else None,
                    user_agent=(request.headers.get("user-agent") or "")[:500] if request else None,
                    details_json=_safe_details(details),
                    created_at=utcnow(),
                )
            )
            db.commit()
    except Exception:
        # Security logging must never disclose secrets or break the primary action.
        return


def record_authenticated_mutation(request: Request, status_code: int) -> None:
    from app.core.config import get_settings
    from app.core.security import token_digest
    from app.db.models import SessionRecord, WorkspaceRecord

    settings = get_settings()
    raw = request.cookies.get(settings.session_cookie_name)
    if not raw:
        return
    Session = get_session_factory()
    with Session() as db:
        session = db.scalar(
            select(SessionRecord).where(
                SessionRecord.token_hash == token_digest(raw), SessionRecord.revoked_at.is_(None)
            )
        )
        if not session:
            return
        workspace = db.get(WorkspaceRecord, session.active_workspace_id) if session.active_workspace_id else None
        record_security_event(
            "http.mutation",
            request=request,
            actor_user_id=session.user_id,
            workspace_id=workspace.id if workspace else None,
            organization_id=workspace.organization_id if workspace else None,
            resource_type="route",
            resource_id=request.url.path,
            outcome="success" if status_code < 400 else "failed",
            details={"method": request.method, "status_code": status_code},
        )
