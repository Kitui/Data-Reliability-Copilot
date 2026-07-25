from __future__ import annotations
from fastapi import Cookie, HTTPException, status
from sqlalchemy import select
from app.core.config import get_settings
from app.core.security import token_digest, utcnow
from app.db.models import OrganizationMembershipRecord, OrganizationRecord, SessionRecord, UserRecord, WorkspaceRecord
from app.db.session import session_scope


def require_user(drc_session: str | None = Cookie(default=None)) -> dict[str, object]:
    settings = get_settings()
    if not drc_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    with session_scope() as db:
        row = db.execute(select(SessionRecord, UserRecord).join(UserRecord, UserRecord.id == SessionRecord.user_id).where(SessionRecord.token_hash == token_digest(drc_session))).first()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid session.")
        session, user = row
        now = utcnow(); expires = session.expires_at
        if expires.tzinfo is None: expires = expires.replace(tzinfo=now.tzinfo)
        if expires <= now or not user.is_active:
            db.delete(session); raise HTTPException(status_code=401, detail="Session expired.")
        session.last_seen_at = now
        workspace = None; membership = None; organization = None
        if session.active_workspace_id:
            workspace = db.get(WorkspaceRecord, session.active_workspace_id)
            if workspace:
                membership = db.scalar(select(OrganizationMembershipRecord).where(OrganizationMembershipRecord.organization_id == workspace.organization_id, OrganizationMembershipRecord.user_id == user.id))
                organization = db.get(OrganizationRecord, workspace.organization_id)
        if not workspace:
            membership = db.scalar(select(OrganizationMembershipRecord).where(OrganizationMembershipRecord.user_id == user.id).order_by(OrganizationMembershipRecord.id))
            if membership:
                workspace = db.scalar(select(WorkspaceRecord).where(WorkspaceRecord.organization_id == membership.organization_id, WorkspaceRecord.is_active == 1).order_by(WorkspaceRecord.id))
                organization = db.get(OrganizationRecord, membership.organization_id)
                if workspace: session.active_workspace_id = workspace.id
        return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role,
                "membership_role": membership.role if membership else None,
                "organization": {"id": organization.id, "name": organization.name, "slug": organization.slug} if organization else None,
                "workspace": {"id": workspace.id, "name": workspace.name, "slug": workspace.slug, "description": workspace.description} if workspace else None}

def require_roles(*allowed: str):
    def dependency(user: dict[str, object] = __import__('fastapi').Depends(require_user)) -> dict[str, object]:
        if user.get("membership_role") not in allowed:
            raise HTTPException(status_code=403, detail="You do not have permission for this action.")
        return user
    return dependency
