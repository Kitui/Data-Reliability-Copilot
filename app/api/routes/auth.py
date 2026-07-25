from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from app.api.auth_dependencies import require_user
from app.core.config import get_settings
from app.core.security import hash_password, new_session_token, session_expiry, token_digest, utcnow, verify_password
from app.db.models import OrganizationMembershipRecord, OrganizationRecord, SessionRecord, UserRecord, WorkspaceRecord
from app.db.session import session_scope
from app.tenancy import slugify

router = APIRouter(prefix="/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=256)

class RegistrationRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    organization_name: str = Field(min_length=2, max_length=255)
    workspace_name: str = Field(default="Reliability Operations", min_length=2, max_length=255)


def _unique_slug(db, model, base: str, organization_id: int | None = None) -> str:
    root = slugify(base)
    candidate = root
    suffix = 2
    while True:
        query = select(model).where(model.slug == candidate)
        if organization_id is not None:
            query = query.where(model.organization_id == organization_id)
        if not db.scalar(query):
            return candidate
        candidate = f"{root}-{suffix}"
        suffix += 1


def _create_session(db, user: UserRecord, workspace: WorkspaceRecord, request: Request) -> tuple[str, object]:
    settings = get_settings()
    token = new_session_token()
    now = utcnow()
    db.execute(delete(SessionRecord).where(SessionRecord.expires_at <= now))
    db.add(SessionRecord(
        user_id=user.id, token_hash=token_digest(token), created_at=now,
        expires_at=session_expiry(settings.session_hours), last_seen_at=now,
        user_agent=(request.headers.get("user-agent") or "")[:500],
        active_workspace_id=workspace.id,
    ))
    user.last_login_at = now
    return token, now


@router.post("/register", status_code=201)
def register(payload: RegistrationRequest, request: Request, response: Response) -> dict[str, object]:
    settings = get_settings()
    email = payload.email.lower().strip()
    full_name = " ".join(payload.full_name.split())
    organization_name = " ".join(payload.organization_name.split())
    workspace_name = " ".join(payload.workspace_name.split())
    with session_scope() as db:
        if db.scalar(select(UserRecord).where(UserRecord.email == email)):
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
        org_slug = _unique_slug(db, OrganizationRecord, organization_name)
        organization = OrganizationRecord(name=organization_name, slug=org_slug, created_at=utcnow())
        db.add(organization); db.flush()
        workspace_slug = _unique_slug(db, WorkspaceRecord, workspace_name, organization.id)
        workspace = WorkspaceRecord(
            organization_id=organization.id, name=workspace_name, slug=workspace_slug,
            description="Primary data reliability workspace", is_active=1, created_at=utcnow(),
        )
        db.add(workspace); db.flush()
        user = UserRecord(
            email=email, full_name=full_name, password_hash=hash_password(payload.password),
            role="admin", is_active=1, created_at=utcnow(),
        )
        db.add(user); db.flush()
        membership = OrganizationMembershipRecord(
            organization_id=organization.id, user_id=user.id, role="owner", created_at=utcnow(),
        )
        db.add(membership)
        token, _ = _create_session(db, user, workspace, request)
    response.set_cookie(
        settings.session_cookie_name, token, max_age=settings.session_hours * 3600,
        httponly=True, secure=settings.secure_cookies, samesite="lax", path="/",
    )
    return {"user": {
        "id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role,
        "membership_role": "owner",
        "organization": {"id": organization.id, "name": organization.name, "slug": organization.slug},
        "workspace": {"id": workspace.id, "name": workspace.name, "slug": workspace.slug, "description": workspace.description},
    }}

@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, object]:
    settings = get_settings()
    with session_scope() as db:
        user = db.scalar(select(UserRecord).where(UserRecord.email == payload.email.lower().strip()))
        if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        token = new_session_token()
        now = utcnow()
        db.execute(delete(SessionRecord).where(SessionRecord.expires_at <= now))
        membership = db.scalar(select(OrganizationMembershipRecord).where(OrganizationMembershipRecord.user_id == user.id).order_by(OrganizationMembershipRecord.id))
        workspace = db.scalar(select(WorkspaceRecord).where(WorkspaceRecord.organization_id == membership.organization_id, WorkspaceRecord.is_active == 1).order_by(WorkspaceRecord.id)) if membership else None
        db.add(SessionRecord(user_id=user.id, token_hash=token_digest(token), created_at=now,
            expires_at=session_expiry(settings.session_hours), last_seen_at=now,
            user_agent=(request.headers.get("user-agent") or "")[:500], active_workspace_id=workspace.id if workspace else None))
        user.last_login_at = now
    response.set_cookie(settings.session_cookie_name, token, max_age=settings.session_hours * 3600,
        httponly=True, secure=settings.secure_cookies, samesite="lax", path="/")
    return {"user": {"email": user.email, "full_name": user.full_name, "role": user.role, "membership_role": membership.role if membership else None, "workspace": {"id": workspace.id, "name": workspace.name, "slug": workspace.slug, "description": workspace.description} if workspace else None}}

@router.get("/me")
def me(user: dict[str, object] = Depends(require_user)) -> dict[str, object]:
    return {"user": user}

@router.post("/logout")
def logout(response: Response, drc_session: str | None = Cookie(default=None)) -> Response:
    settings = get_settings()
    if drc_session:
        with session_scope() as db:
            db.execute(delete(SessionRecord).where(SessionRecord.token_hash == token_digest(drc_session)))
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.status_code = 204
    return response
