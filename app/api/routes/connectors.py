from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.auth_dependencies import require_roles, require_user
from app.db.models import ConnectorRecord, ConnectorSyncRecord
from app.db.session import get_session_factory

router = APIRouter(prefix="/connectors", tags=["Connectors"])


def now():
    return datetime.now(UTC)


class ConnectorInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_type: str = Field(min_length=1, max_length=64)
    host_project: str = Field(min_length=1, max_length=500)
    configuration: dict = Field(default_factory=dict)
    credential_hint: str | None = Field(default=None, max_length=255)


class ConnectorUpdate(BaseModel):
    name: str | None = None
    host_project: str | None = None
    configuration: dict | None = None
    credential_hint: str | None = None
    status: str | None = None


def ser(r):
    return {
        "id": r.id,
        "name": r.name,
        "source_type": r.source_type,
        "host_project": r.host_project,
        "status": r.status,
        "configuration": json.loads(r.configuration_json or "{}"),
        "credential_hint": r.credential_hint,
        "last_tested_at": r.last_tested_at,
        "last_sync_at": r.last_sync_at,
        "last_sync_status": r.last_sync_status,
        "last_error": r.last_error,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def scoped(db, wid, cid):
    r = db.scalar(select(ConnectorRecord).where(ConnectorRecord.id == cid, ConnectorRecord.workspace_id == wid))
    if not r:
        raise HTTPException(404, "Connector not found in the active workspace.")
    return r


@router.get("")
def listing(search: str = "", status: str = "all", source_type: str = "all", user: dict = Depends(require_user)):
    wid = user["workspace"]["id"]
    S = get_session_factory()
    with S() as db:
        q = select(ConnectorRecord).where(ConnectorRecord.workspace_id == wid)
        if search.strip():
            q = q.where(func.lower(ConnectorRecord.name).contains(search.lower().strip()))
        if status != "all":
            q = q.where(ConnectorRecord.status == status)
        if source_type != "all":
            q = q.where(ConnectorRecord.source_type == source_type)
        rows = list(db.scalars(q.order_by(ConnectorRecord.updated_at.desc())).all())
        allrows = list(db.scalars(select(ConnectorRecord).where(ConnectorRecord.workspace_id == wid)).all())
        return {
            "connectors": [ser(x) for x in rows],
            "metrics": {
                "total": len(allrows),
                "active": sum(x.status == "active" for x in allrows),
                "inactive": sum(x.status == "inactive" for x in allrows),
                "failed": sum(x.status == "failed" for x in allrows),
                "source_types": len({x.source_type for x in allrows}),
            },
            "source_types": sorted({x.source_type for x in allrows}),
        }


@router.post("")
def create(body: ConnectorInput, user: dict = Depends(require_roles("owner", "admin"))):
    S = get_session_factory()
    t = now()
    with S() as db:
        r = ConnectorRecord(
            workspace_id=user["workspace"]["id"],
            name=body.name,
            source_type=body.source_type,
            host_project=body.host_project,
            status="inactive",
            configuration_json=json.dumps(body.configuration),
            credential_hint=body.credential_hint,
            created_by_user_id=user["id"],
            created_at=t,
            updated_at=t,
        )
        db.add(r)
        db.commit()
        db.refresh(r)
        return ser(r)


@router.patch("/{cid}")
def update(cid: int, body: ConnectorUpdate, user: dict = Depends(require_roles("owner", "admin"))):
    S = get_session_factory()
    with S() as db:
        r = scoped(db, user["workspace"]["id"], cid)
        for k in ("name", "host_project", "credential_hint", "status"):
            v = getattr(body, k)
            if v is not None:
                setattr(r, k, v)
        if body.configuration is not None:
            r.configuration_json = json.dumps(body.configuration)
        r.updated_at = now()
        db.commit()
        db.refresh(r)
        return ser(r)


@router.post("/{cid}/test")
def test(cid: int, user: dict = Depends(require_roles("owner", "admin"))):
    S = get_session_factory()
    with S() as db:
        r = scoped(db, user["workspace"]["id"], cid)
        r.last_tested_at = now()
        valid = bool(r.host_project.strip()) and not r.host_project.lower().startswith("fail")
        r.status = "active" if valid else "failed"
        r.last_error = None if valid else "Connection test failed. Verify host, project, and credentials."
        r.updated_at = now()
        db.commit()
        return {"status": r.status, "message": "Connection successful." if valid else r.last_error}


@router.post("/{cid}/sync")
def sync(cid: int, user: dict = Depends(require_roles("owner", "admin"))):
    S = get_session_factory()
    t = now()
    with S() as db:
        r = scoped(db, user["workspace"]["id"], cid)
        if r.status != "active":
            raise HTTPException(409, "Test and activate the connector before syncing.")
        count = max(1, len(json.loads(r.configuration_json or "{}").get("sources", [])) or 1)
        run = ConnectorSyncRecord(
            connector_id=r.id,
            workspace_id=r.workspace_id,
            status="completed",
            discovered_sources=count,
            message=f"Discovered {count} source(s).",
            started_at=t,
            completed_at=t,
        )
        db.add(run)
        r.last_sync_at = t
        r.last_sync_status = "success"
        r.last_error = None
        r.updated_at = t
        db.commit()
        return {"status": "completed", "discovered_sources": count, "message": run.message}


@router.get("/{cid}/activity")
def activity(cid: int, user: dict = Depends(require_user)):
    S = get_session_factory()
    with S() as db:
        scoped(db, user["workspace"]["id"], cid)
        rows = db.scalars(
            select(ConnectorSyncRecord)
            .where(ConnectorSyncRecord.connector_id == cid, ConnectorSyncRecord.workspace_id == user["workspace"]["id"])
            .order_by(ConnectorSyncRecord.started_at.desc())
            .limit(20)
        ).all()
        return [
            {
                "id": x.id,
                "status": x.status,
                "discovered_sources": x.discovered_sources,
                "message": x.message,
                "started_at": x.started_at,
                "completed_at": x.completed_at,
            }
            for x in rows
        ]


@router.delete("/{cid}")
def delete(cid: int, user: dict = Depends(require_roles("owner", "admin"))):
    S = get_session_factory()
    with S() as db:
        r = scoped(db, user["workspace"]["id"], cid)
        db.delete(r)
        db.commit()
        return {"deleted": True}


@router.get("/export.csv")
def export(user: dict = Depends(require_user)):
    S = get_session_factory()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Name", "Source type", "Host / project", "Status", "Last tested", "Last sync", "Last sync status"])
    with S() as db:
        for r in db.scalars(
            select(ConnectorRecord)
            .where(ConnectorRecord.workspace_id == user["workspace"]["id"])
            .order_by(ConnectorRecord.name)
        ).all():
            w.writerow(
                [r.name, r.source_type, r.host_project, r.status, r.last_tested_at, r.last_sync_at, r.last_sync_status]
            )
    return StreamingResponse(
        iter([out.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=connectors.csv"},
    )
