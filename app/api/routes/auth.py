from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from app.api.auth_dependencies import require_user
from app.core.config import get_settings
from app.core.password_policy import validate_password
from app.core.security import hash_password, new_session_token, session_expiry, token_digest, utcnow, verify_password
from app.db.models import (
    AccountTokenRecord,
    LoginAttemptRecord,
    OrganizationMembershipRecord,
    OrganizationRecord,
    SessionRecord,
    UserRecord,
    WorkspaceRecord,
)
from app.db.session import session_scope
from app.services.security_audit import record_security_event
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


class TokenRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)


class TokenConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=500)
    password: str | None = Field(default=None, min_length=8, max_length=256)


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()[:64]
    return request.client.host[:64] if request.client else None


def _set_auth_cookies(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        new_session_token(),
        max_age=settings.session_hours * 3600,
        httponly=False,
        secure=settings.secure_cookies,
        samesite="strict",
        path="/",
    )


def _password_or_400(password: str) -> None:
    errors = validate_password(password)
    if errors:
        raise HTTPException(status_code=400, detail={"message": "Password does not meet security requirements.", "requirements": errors})


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


def _create_session(db, user: UserRecord, workspace: WorkspaceRecord | None, request: Request) -> str:
    settings = get_settings()
    token = new_session_token()
    now = utcnow()
    db.execute(delete(SessionRecord).where(SessionRecord.expires_at <= now))
    db.add(SessionRecord(
        user_id=user.id,
        token_hash=token_digest(token),
        created_at=now,
        expires_at=session_expiry(settings.session_hours),
        last_seen_at=now,
        user_agent=(request.headers.get("user-agent") or "")[:500],
        active_workspace_id=workspace.id if workspace else None,
        ip_address=_client_ip(request),
    ))
    user.last_login_at = now
    return token


def _issue_account_token(db, user_id: int, purpose: str, minutes: int) -> str:
    raw = new_session_token()
    now = utcnow()
    db.execute(delete(AccountTokenRecord).where(AccountTokenRecord.user_id == user_id, AccountTokenRecord.purpose == purpose, AccountTokenRecord.used_at.is_(None)))
    db.add(AccountTokenRecord(user_id=user_id, purpose=purpose, token_hash=token_digest(raw), created_at=now, expires_at=now + timedelta(minutes=minutes)))
    return raw


@router.post("/register", status_code=201)
def register(payload: RegistrationRequest, request: Request, response: Response) -> dict[str, object]:
    settings = get_settings()
    _password_or_400(payload.password)
    email = payload.email.lower().strip()
    full_name = " ".join(payload.full_name.split())
    organization_name = " ".join(payload.organization_name.split())
    workspace_name = " ".join(payload.workspace_name.split())
    with session_scope() as db:
        if db.scalar(select(UserRecord).where(UserRecord.email == email)):
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
        organization = OrganizationRecord(name=organization_name, slug=_unique_slug(db, OrganizationRecord, organization_name), created_at=utcnow())
        db.add(organization); db.flush()
        workspace = WorkspaceRecord(organization_id=organization.id, name=workspace_name, slug=_unique_slug(db, WorkspaceRecord, workspace_name, organization.id), description="Primary data reliability workspace", is_active=1, created_at=utcnow())
        db.add(workspace); db.flush()
        user = UserRecord(email=email, full_name=full_name, password_hash=hash_password(payload.password), role="admin", is_active=1, created_at=utcnow(), email_verified_at=None if settings.require_email_verification else utcnow())
        db.add(user); db.flush()
        db.add(OrganizationMembershipRecord(organization_id=organization.id, user_id=user.id, role="owner", created_at=utcnow()))
        token = _create_session(db, user, workspace, request)
        verification_token = _issue_account_token(db, user.id, "email_verification", 1440) if settings.require_email_verification else None
    _set_auth_cookies(response, token)
    record_security_event("account.register", request=request, actor_user_id=user.id, organization_id=organization.id, workspace_id=workspace.id, resource_type="user", resource_id=user.id)
    result: dict[str, object] = {"user": {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role, "membership_role": "owner", "email_verified": bool(user.email_verified_at), "organization": {"id": organization.id, "name": organization.name, "slug": organization.slug}, "workspace": {"id": workspace.id, "name": workspace.name, "slug": workspace.slug, "description": workspace.description}}}
    if verification_token and settings.expose_dev_tokens and not settings.is_production:
        result["development_verification_token"] = verification_token
    return result


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, object]:
    settings = get_settings()
    email = payload.email.lower().strip()
    ip = _client_ip(request)
    now = utcnow()
    window_start = now - timedelta(minutes=settings.login_window_minutes)
    failure_status: int | None = None
    failure_detail: str | None = None
    with session_scope() as db:
        recent_failures = db.scalar(select(func.count(LoginAttemptRecord.id)).where(LoginAttemptRecord.email == email, LoginAttemptRecord.succeeded == 0, LoginAttemptRecord.attempted_at >= window_start)) or 0
        user = db.scalar(select(UserRecord).where(UserRecord.email == email))
        if recent_failures >= settings.login_max_attempts or (user and user.locked_until and user.locked_until > now):
            failure_status, failure_detail = 429, "Too many failed login attempts. Try again later."
            membership = workspace = token = None
        else:
            valid = bool(user and user.is_active and verify_password(payload.password, user.password_hash))
            db.add(LoginAttemptRecord(email=email, ip_address=ip, succeeded=1 if valid else 0, attempted_at=now, user_agent=(request.headers.get("user-agent") or "")[:500]))
            if not valid:
                if user and recent_failures + 1 >= settings.login_max_attempts:
                    user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
                failure_status, failure_detail = 401, "Invalid email or password."
                membership = workspace = token = None
            elif settings.require_email_verification and not user.email_verified_at:
                failure_status, failure_detail = 403, "Email verification is required before login."
                membership = workspace = token = None
            else:
                user.locked_until = None
                membership = db.scalar(select(OrganizationMembershipRecord).where(OrganizationMembershipRecord.user_id == user.id).order_by(OrganizationMembershipRecord.id))
                workspace = db.scalar(select(WorkspaceRecord).where(WorkspaceRecord.organization_id == membership.organization_id, WorkspaceRecord.is_active == 1).order_by(WorkspaceRecord.id)) if membership else None
                token = _create_session(db, user, workspace, request)
    if failure_status:
        record_security_event("auth.login", request=request, actor_user_id=user.id if user else None, outcome="blocked" if failure_status == 429 else "failed", details={"email": email})
        raise HTTPException(status_code=failure_status, detail=failure_detail)
    _set_auth_cookies(response, token)
    record_security_event("auth.login", request=request, actor_user_id=user.id, organization_id=membership.organization_id if membership else None, workspace_id=workspace.id if workspace else None)
    return {"user": {"email": user.email, "full_name": user.full_name, "role": user.role, "membership_role": membership.role if membership else None, "email_verified": bool(user.email_verified_at), "workspace": {"id": workspace.id, "name": workspace.name, "slug": workspace.slug, "description": workspace.description} if workspace else None}}


@router.get("/me")
def me(user: dict[str, object] = Depends(require_user)) -> dict[str, object]:
    return {"user": user}


@router.get("/sessions")
def sessions(user: dict[str, object] = Depends(require_user)) -> list[dict[str, object]]:
    with session_scope() as db:
        rows = db.scalars(select(SessionRecord).where(SessionRecord.user_id == user["id"], SessionRecord.revoked_at.is_(None)).order_by(SessionRecord.created_at.desc())).all()
        return [{"id": row.id, "created_at": row.created_at, "last_seen_at": row.last_seen_at, "expires_at": row.expires_at, "ip_address": row.ip_address, "user_agent": row.user_agent} for row in rows]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(session_id: int, request: Request, user: dict[str, object] = Depends(require_user)) -> Response:
    with session_scope() as db:
        row = db.scalar(select(SessionRecord).where(SessionRecord.id == session_id, SessionRecord.user_id == user["id"]))
        if row is None: raise HTTPException(404, "Session not found.")
        row.revoked_at = utcnow()
    record_security_event("auth.session_revoke", request=request, user=user, resource_type="session", resource_id=session_id)
    return Response(status_code=204)


@router.post("/sessions/revoke-all", status_code=204)
def revoke_all_sessions(request: Request, user: dict[str, object] = Depends(require_user)) -> Response:
    with session_scope() as db:
        rows = db.scalars(select(SessionRecord).where(SessionRecord.user_id == user["id"], SessionRecord.revoked_at.is_(None))).all()
        for row in rows: row.revoked_at = utcnow()
    record_security_event("auth.sessions_revoke_all", request=request, user=user)
    return Response(status_code=204)


@router.post("/password-reset/request")
def request_password_reset(payload: TokenRequest, request: Request) -> dict[str, object]:
    settings = get_settings(); raw = None
    with session_scope() as db:
        user = db.scalar(select(UserRecord).where(UserRecord.email == payload.email.lower().strip()))
        if user and user.is_active: raw = _issue_account_token(db, user.id, "password_reset", 30)
    record_security_event("auth.password_reset_request", request=request, actor_user_id=user.id if user else None)
    result: dict[str, object] = {"message": "If the account exists, password-reset instructions have been generated."}
    if raw and settings.expose_dev_tokens and not settings.is_production: result["development_token"] = raw
    return result


@router.post("/password-reset/confirm")
def confirm_password_reset(payload: TokenConfirm, request: Request) -> dict[str, str]:
    if not payload.password: raise HTTPException(400, "A new password is required.")
    _password_or_400(payload.password)
    now = utcnow()
    with session_scope() as db:
        token = db.scalar(select(AccountTokenRecord).where(AccountTokenRecord.token_hash == token_digest(payload.token), AccountTokenRecord.purpose == "password_reset", AccountTokenRecord.used_at.is_(None)))
        if not token or token.expires_at <= now: raise HTTPException(400, "The reset token is invalid or expired.")
        user = db.get(UserRecord, token.user_id); user.password_hash = hash_password(payload.password); user.locked_until = None; token.used_at = now
        db.execute(delete(SessionRecord).where(SessionRecord.user_id == user.id))
    record_security_event("auth.password_reset", request=request, actor_user_id=user.id, resource_type="user", resource_id=user.id)
    return {"message": "Password updated. Sign in again on all devices."}


@router.post("/email-verification/request")
def request_email_verification(request: Request, user: dict[str, object] = Depends(require_user)) -> dict[str, object]:
    settings = get_settings(); raw = None
    with session_scope() as db:
        row = db.get(UserRecord, user["id"])
        if row and not row.email_verified_at: raw = _issue_account_token(db, row.id, "email_verification", 1440)
    result: dict[str, object] = {"message": "Verification instructions have been generated if required."}
    if raw and settings.expose_dev_tokens and not settings.is_production: result["development_token"] = raw
    return result


@router.post("/email-verification/confirm")
def confirm_email_verification(payload: TokenConfirm, request: Request) -> dict[str, str]:
    now = utcnow()
    with session_scope() as db:
        token = db.scalar(select(AccountTokenRecord).where(AccountTokenRecord.token_hash == token_digest(payload.token), AccountTokenRecord.purpose == "email_verification", AccountTokenRecord.used_at.is_(None)))
        if not token or token.expires_at <= now: raise HTTPException(400, "The verification token is invalid or expired.")
        user = db.get(UserRecord, token.user_id); user.email_verified_at = now; token.used_at = now
    record_security_event("auth.email_verified", request=request, actor_user_id=user.id, resource_type="user", resource_id=user.id)
    return {"message": "Email address verified."}


@router.post("/logout")
def logout(request: Request, response: Response, drc_session: str | None = Cookie(default=None)) -> Response:
    settings = get_settings()
    if drc_session:
        with session_scope() as db:
            row = db.scalar(select(SessionRecord).where(SessionRecord.token_hash == token_digest(drc_session)))
            actor = row.user_id if row else None
            if row: row.revoked_at = utcnow()
        record_security_event("auth.logout", request=request, actor_user_id=actor)
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
    response.status_code = 204
    return response
