from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select

from app.api.auth_dependencies import require_roles, require_user
from app.core.security import hash_password, token_digest, utcnow
from app.db.models import OrganizationMembershipRecord, TeamInvitationRecord, UserRecord
from app.db.session import session_scope

router = APIRouter(prefix="/team", tags=["Team Management"])
VALID_ROLES = {"owner", "admin", "analyst", "viewer"}


class InvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    full_name: str = Field(min_length=2, max_length=255)
    role: str = Field(default="analyst")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email:
            raise ValueError("Enter a valid email address.")
        local, domain = email.rsplit("@", 1)
        if not local or not domain or "." not in domain:
            raise ValueError("Enter a valid email address.")
        if any(char.isspace() for char in email):
            raise ValueError("Email addresses cannot contain spaces.")
        return email


class InvitationAccept(BaseModel):
    token: str = Field(min_length=20)
    password: str = Field(min_length=8, max_length=256)


class RoleUpdate(BaseModel):
    role: str


class MemberStatusUpdate(BaseModel):
    is_active: bool


def _validate_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Role must be owner, admin, analyst, or viewer.")
    return normalized


def _member_payload(membership: OrganizationMembershipRecord, user: UserRecord) -> dict[str, object]:
    return {
        "membership_id": membership.id,
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": membership.role,
        "is_active": bool(user.is_active),
        "joined_at": membership.created_at,
        "last_login_at": user.last_login_at,
    }


@router.get("/members")
def list_members(current: dict[str, object] = Depends(require_user)) -> list[dict[str, object]]:
    organization = current.get("organization")
    if not organization:
        return []
    with session_scope() as db:
        rows = db.execute(
            select(OrganizationMembershipRecord, UserRecord)
            .join(UserRecord, UserRecord.id == OrganizationMembershipRecord.user_id)
            .where(OrganizationMembershipRecord.organization_id == organization["id"])
            .order_by(UserRecord.full_name)
        ).all()
        return [_member_payload(membership, user) for membership, user in rows]


@router.get("/invitations")
def list_invitations(current: dict[str, object] = Depends(require_roles("owner", "admin"))) -> list[dict[str, object]]:
    organization_id = current["organization"]["id"]
    now = utcnow()
    with session_scope() as db:
        invitations = db.scalars(
            select(TeamInvitationRecord)
            .where(TeamInvitationRecord.organization_id == organization_id)
            .order_by(TeamInvitationRecord.created_at.desc())
        ).all()
        output = []
        for invitation in invitations:
            status = invitation.status
            expires_at = invitation.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=now.tzinfo)
            if status == "pending" and expires_at <= now:
                invitation.status = status = "expired"
            output.append(
                {
                    "id": invitation.id,
                    "email": invitation.email,
                    "full_name": invitation.full_name,
                    "role": invitation.role,
                    "status": status,
                    "created_at": invitation.created_at,
                    "expires_at": invitation.expires_at,
                }
            )
        return output


@router.post("/invitations", status_code=201)
def create_invitation(
    payload: InvitationCreate, current: dict[str, object] = Depends(require_roles("owner", "admin"))
) -> dict[str, object]:
    role = _validate_role(payload.role)
    if current["membership_role"] == "admin" and role == "owner":
        raise HTTPException(status_code=403, detail="Only an owner can invite another owner.")
    organization_id = current["organization"]["id"]
    email = payload.email.lower().strip()
    token = secrets.token_urlsafe(32)
    now = utcnow()
    with session_scope() as db:
        existing_user = db.scalar(select(UserRecord).where(UserRecord.email == email))
        if existing_user:
            existing_membership = db.scalar(
                select(OrganizationMembershipRecord).where(
                    OrganizationMembershipRecord.organization_id == organization_id,
                    OrganizationMembershipRecord.user_id == existing_user.id,
                )
            )
            if existing_membership:
                raise HTTPException(status_code=409, detail="This user is already a member of the organization.")
        pending = db.scalar(
            select(TeamInvitationRecord).where(
                TeamInvitationRecord.organization_id == organization_id,
                TeamInvitationRecord.email == email,
                TeamInvitationRecord.status == "pending",
            )
        )
        if pending:
            pending.status = "revoked"
        invitation = TeamInvitationRecord(
            organization_id=organization_id,
            invited_by_user_id=current["id"],
            email=email,
            full_name=payload.full_name.strip(),
            role=role,
            token_hash=token_digest(token),
            status="pending",
            created_at=now,
            expires_at=now + timedelta(days=7),
        )
        db.add(invitation)
        db.flush()
        return {
            "id": invitation.id,
            "email": invitation.email,
            "full_name": invitation.full_name,
            "role": invitation.role,
            "status": invitation.status,
            "expires_at": invitation.expires_at,
            "token": token,
            "acceptance_path": f"/?invite={token}",
        }


@router.post("/invitations/accept", status_code=201)
def accept_invitation(payload: InvitationAccept) -> dict[str, object]:
    now = utcnow()
    with session_scope() as db:
        invitation = db.scalar(
            select(TeamInvitationRecord).where(TeamInvitationRecord.token_hash == token_digest(payload.token))
        )
        if not invitation or invitation.status != "pending":
            raise HTTPException(status_code=400, detail="Invitation is invalid or no longer available.")
        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=now.tzinfo)
        if expires_at <= now:
            invitation.status = "expired"
            raise HTTPException(status_code=400, detail="Invitation has expired.")
        user = db.scalar(select(UserRecord).where(UserRecord.email == invitation.email))
        if not user:
            user = UserRecord(
                email=invitation.email,
                full_name=invitation.full_name,
                password_hash=hash_password(payload.password),
                role="user",
                is_active=1,
                created_at=now,
            )
            db.add(user)
            db.flush()
        membership = db.scalar(
            select(OrganizationMembershipRecord).where(
                OrganizationMembershipRecord.organization_id == invitation.organization_id,
                OrganizationMembershipRecord.user_id == user.id,
            )
        )
        if not membership:
            membership = OrganizationMembershipRecord(
                organization_id=invitation.organization_id,
                user_id=user.id,
                role=invitation.role,
                created_at=now,
            )
            db.add(membership)
        invitation.status = "accepted"
        invitation.accepted_at = now
        return {
            "email": user.email,
            "full_name": user.full_name,
            "role": invitation.role,
            "message": "Invitation accepted. You can now sign in.",
        }


@router.patch("/members/{membership_id}/role")
def update_member_role(
    membership_id: int, payload: RoleUpdate, current: dict[str, object] = Depends(require_roles("owner", "admin"))
) -> dict[str, object]:
    role = _validate_role(payload.role)
    organization_id = current["organization"]["id"]
    with session_scope() as db:
        membership = db.get(OrganizationMembershipRecord, membership_id)
        if not membership or membership.organization_id != organization_id:
            raise HTTPException(status_code=404, detail="Team member not found.")
        if current["membership_role"] == "admin" and (membership.role == "owner" or role == "owner"):
            raise HTTPException(status_code=403, detail="Administrators cannot manage owner roles.")
        if membership.user_id == current["id"] and membership.role == "owner" and role != "owner":
            owner_count = db.scalar(
                select(func.count())
                .select_from(OrganizationMembershipRecord)
                .where(
                    OrganizationMembershipRecord.organization_id == organization_id,
                    OrganizationMembershipRecord.role == "owner",
                )
            )
            if owner_count <= 1:
                raise HTTPException(status_code=409, detail="The organization must retain at least one owner.")
        membership.role = role
        user = db.get(UserRecord, membership.user_id)
        return _member_payload(membership, user)


@router.patch("/members/{membership_id}/status")
def update_member_status(
    membership_id: int,
    payload: MemberStatusUpdate,
    current: dict[str, object] = Depends(require_roles("owner", "admin")),
) -> dict[str, object]:
    organization_id = current["organization"]["id"]
    with session_scope() as db:
        membership = db.get(OrganizationMembershipRecord, membership_id)
        if not membership or membership.organization_id != organization_id:
            raise HTTPException(status_code=404, detail="Team member not found.")
        if membership.user_id == current["id"] and not payload.is_active:
            raise HTTPException(status_code=409, detail="You cannot deactivate your own account.")
        if current["membership_role"] == "admin" and membership.role == "owner":
            raise HTTPException(status_code=403, detail="Administrators cannot deactivate an owner.")
        user = db.get(UserRecord, membership.user_id)
        user.is_active = 1 if payload.is_active else 0
        return _member_payload(membership, user)


@router.delete("/invitations/{invitation_id}")
def revoke_invitation(
    invitation_id: int, current: dict[str, object] = Depends(require_roles("owner", "admin"))
) -> dict[str, str]:
    organization_id = current["organization"]["id"]
    with session_scope() as db:
        invitation = db.get(TeamInvitationRecord, invitation_id)
        if not invitation or invitation.organization_id != organization_id:
            raise HTTPException(status_code=404, detail="Invitation not found.")
        if invitation.status == "pending":
            invitation.status = "revoked"
        return {"status": "revoked"}
