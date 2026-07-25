from __future__ import annotations

import re

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import utcnow
from app.db.models import OrganizationMembershipRecord, OrganizationRecord, UserRecord, WorkspaceRecord
from app.db.session import session_scope

ROLES = {"owner", "admin", "analyst", "viewer"}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "workspace"


def ensure_bootstrap_tenant() -> None:
    settings = get_settings()
    with session_scope() as db:
        user = db.scalar(select(UserRecord).where(UserRecord.email == settings.bootstrap_admin_email.lower().strip()))
        if not user:
            return
        org = db.scalar(select(OrganizationRecord).where(OrganizationRecord.slug == "drc-organization"))
        if not org:
            org = OrganizationRecord(name="DRC Organization", slug="drc-organization", created_at=utcnow())
            db.add(org)
            db.flush()
        membership = db.scalar(
            select(OrganizationMembershipRecord).where(
                OrganizationMembershipRecord.organization_id == org.id, OrganizationMembershipRecord.user_id == user.id
            )
        )
        if not membership:
            db.add(
                OrganizationMembershipRecord(organization_id=org.id, user_id=user.id, role="owner", created_at=utcnow())
            )
        workspace = db.scalar(
            select(WorkspaceRecord).where(
                WorkspaceRecord.organization_id == org.id, WorkspaceRecord.slug == "reliability-operations"
            )
        )
        if not workspace:
            workspace = WorkspaceRecord(
                organization_id=org.id,
                name="Reliability Operations",
                slug="reliability-operations",
                description="Primary data reliability workspace",
                is_active=1,
                created_at=utcnow(),
            )
            db.add(workspace)
            db.flush()
        from app.db.models import AuditRecord

        for audit in db.scalars(select(AuditRecord).where(AuditRecord.workspace_id.is_(None))).all():
            audit.workspace_id = workspace.id
