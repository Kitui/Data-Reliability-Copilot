from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.db.models import IssueActivityRecord
from app.db.session import session_scope
from app.schemas import IssueLifecycleActivity


def utcnow() -> datetime:
    return datetime.now(UTC)


def record_activity(
    *,
    audit_id: str,
    issue_id: str,
    workspace_id: int,
    actor_user_id: int | None,
    actor_name: str | None,
    action: str,
    field_name: str | None = None,
    previous_value: Any = None,
    new_value: Any = None,
    note: str | None = None,
) -> IssueLifecycleActivity:
    with session_scope() as db:
        row = IssueActivityRecord(
            audit_id=audit_id,
            issue_id=issue_id,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            actor_name=actor_name,
            action=action,
            field_name=field_name,
            previous_value=None if previous_value is None else str(previous_value),
            new_value=None if new_value is None else str(new_value),
            note=note,
            created_at=utcnow(),
        )
        db.add(row)
        db.flush()
        return IssueLifecycleActivity.model_validate(
            {
                "id": row.id,
                "audit_id": row.audit_id,
                "issue_id": row.issue_id,
                "action": row.action,
                "field_name": row.field_name,
                "previous_value": row.previous_value,
                "new_value": row.new_value,
                "note": row.note,
                "actor_user_id": row.actor_user_id,
                "actor_name": row.actor_name,
                "created_at": row.created_at,
            }
        )


def list_activities(audit_id: str, issue_id: str, workspace_id: int) -> list[IssueLifecycleActivity]:
    with session_scope() as db:
        rows = db.scalars(
            select(IssueActivityRecord)
            .where(
                IssueActivityRecord.audit_id == audit_id,
                IssueActivityRecord.issue_id == issue_id,
                IssueActivityRecord.workspace_id == workspace_id,
            )
            .order_by(IssueActivityRecord.created_at.desc(), IssueActivityRecord.id.desc())
        ).all()
        return [
            IssueLifecycleActivity.model_validate(
                {
                    "id": row.id,
                    "audit_id": row.audit_id,
                    "issue_id": row.issue_id,
                    "action": row.action,
                    "field_name": row.field_name,
                    "previous_value": row.previous_value,
                    "new_value": row.new_value,
                    "note": row.note,
                    "actor_user_id": row.actor_user_id,
                    "actor_name": row.actor_name,
                    "created_at": row.created_at,
                }
            )
            for row in rows
        ]
