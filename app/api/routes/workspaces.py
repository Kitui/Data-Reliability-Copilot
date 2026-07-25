from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.auth_dependencies import require_roles, require_user
from app.core.security import token_digest, utcnow
from app.db.models import OrganizationMembershipRecord, SessionRecord, WorkspaceRecord
from app.db.session import session_scope
from app.tenancy import slugify

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=500)


@router.get("")
def list_workspaces(user: dict[str, object] = Depends(require_user)) -> list[dict[str, object]]:
    org = user.get("organization")
    if not org:
        return []
    with session_scope() as db:
        rows = db.scalars(
            select(WorkspaceRecord)
            .where(WorkspaceRecord.organization_id == org["id"], WorkspaceRecord.is_active == 1)
            .order_by(WorkspaceRecord.name)
        ).all()
        active_id = (user.get("workspace") or {}).get("id")
        return [
            {"id": w.id, "name": w.name, "slug": w.slug, "description": w.description, "active": w.id == active_id}
            for w in rows
        ]


@router.post("")
def create_workspace(
    payload: WorkspaceCreate, user: dict[str, object] = Depends(require_roles("owner", "admin"))
) -> dict[str, object]:
    org_id = user["organization"]["id"]
    with session_scope() as db:
        base = slugify(payload.name)
        slug = base
        suffix = 2
        while db.scalar(
            select(WorkspaceRecord).where(WorkspaceRecord.organization_id == org_id, WorkspaceRecord.slug == slug)
        ):
            slug = f"{base}-{suffix}"
            suffix += 1
        workspace = WorkspaceRecord(
            organization_id=org_id,
            name=payload.name.strip(),
            slug=slug,
            description=payload.description,
            is_active=1,
            created_at=utcnow(),
        )
        db.add(workspace)
        db.flush()
        return {
            "id": workspace.id,
            "name": workspace.name,
            "slug": workspace.slug,
            "description": workspace.description,
        }


@router.post("/{workspace_id}/activate")
def activate_workspace(
    workspace_id: int, drc_session: str | None = Cookie(default=None), user: dict[str, object] = Depends(require_user)
) -> dict[str, object]:
    if not drc_session:
        raise HTTPException(status_code=401, detail="Authentication required.")
    with session_scope() as db:
        workspace = db.get(WorkspaceRecord, workspace_id)
        if not workspace or not workspace.is_active:
            raise HTTPException(status_code=404, detail="Workspace not found.")
        membership = db.scalar(
            select(OrganizationMembershipRecord).where(
                OrganizationMembershipRecord.organization_id == workspace.organization_id,
                OrganizationMembershipRecord.user_id == user["id"],
            )
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Workspace access denied.")
        session = db.scalar(select(SessionRecord).where(SessionRecord.token_hash == token_digest(drc_session)))
        if not session:
            raise HTTPException(status_code=401, detail="Invalid session.")
        session.active_workspace_id = workspace.id
        return {
            "workspace": {
                "id": workspace.id,
                "name": workspace.name,
                "slug": workspace.slug,
                "description": workspace.description,
            }
        }
