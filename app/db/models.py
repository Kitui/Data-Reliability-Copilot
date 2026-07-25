from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AuditRecord(Base):
    __tablename__ = "audits"

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    issue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary_source: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)

    issues: Mapped[list[IssueRecord]] = relationship(
        back_populates="audit", cascade="all, delete-orphan", passive_deletes=True
    )
    upload: Mapped[UploadRecord | None] = relationship(
        back_populates="audit", cascade="all, delete-orphan", uselist=False, passive_deletes=True
    )


class IssueRecord(Base):
    __tablename__ = "audit_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_id: Mapped[str] = mapped_column(ForeignKey("audits.audit_id", ondelete="CASCADE"), nullable=False, index=True)
    issue_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(255))
    affected_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    affected_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    audit: Mapped[AuditRecord] = relationship(back_populates="issues")


class UploadRecord(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_id: Mapped[str] = mapped_column(
        ForeignKey("audits.audit_id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    relative_path: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    storage_backend: Mapped[str] = mapped_column(String(24), nullable=False, default="local")
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    display_name: Mapped[str | None] = mapped_column(String(255))

    audit: Mapped[AuditRecord] = relationship(back_populates="upload")


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="admin")
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    memberships: Mapped[list[OrganizationMembershipRecord]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    sessions: Mapped[list[SessionRecord]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class SessionRecord(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500))
    active_workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    user: Mapped[UserRecord] = relationship(back_populates="sessions")


class LoginAttemptRecord(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), index=True)
    succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(500))


class AccountTokenRecord(Base):
    __tablename__ = "account_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdministrativeAuditLogRecord(Base):
    __tablename__ = "administrative_audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(80), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(120))
    outcome: Mapped[str] = mapped_column(String(24), nullable=False, default="success", index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class OrganizationRecord(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    workspaces: Mapped[list[WorkspaceRecord]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    memberships: Mapped[list[OrganizationMembershipRecord]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class WorkspaceRecord(Base):
    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_workspaces_org_slug"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    organization: Mapped[OrganizationRecord] = relationship(back_populates="workspaces")


class OrganizationMembershipRecord(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    organization: Mapped[OrganizationRecord] = relationship(back_populates="memberships")
    user: Mapped[UserRecord] = relationship(back_populates="memberships")


class TeamInvitationRecord(Base):
    __tablename__ = "team_invitations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invited_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DatasetRecord(Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_datasets_workspace_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(120), nullable=False, default="General")
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Unassigned")
    environment: Mapped[str] = mapped_column(String(32), nullable=False, default="production")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="registered", index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="CSV")
    description: Mapped[str | None] = mapped_column(String(800))
    labels_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quality_score: Mapped[int | None] = mapped_column(Integer)
    issue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latest_audit_id: Mapped[str | None] = mapped_column(ForeignKey("audits.audit_id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IssueActivityRecord(Base):
    __tablename__ = "issue_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_id: Mapped[str] = mapped_column(ForeignKey("audits.audit_id", ondelete="CASCADE"), nullable=False, index=True)
    issue_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    actor_name: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    field_name: Mapped[str | None] = mapped_column(String(64))
    previous_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class QualityRuleRecord(Base):
    __tablename__ = "quality_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(800))
    rule_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="column")
    column_name: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="validity")
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    recommendation: Mapped[str | None] = mapped_column(String(1000))
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DatasetRuleAssignmentRecord(Base):
    __tablename__ = "dataset_rule_assignments"
    __table_args__ = (UniqueConstraint("dataset_id", "rule_id", name="uq_dataset_rule_assignment"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("quality_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RuleExecutionRecord(Base):
    __tablename__ = "rule_executions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_id: Mapped[str] = mapped_column(ForeignKey("audits.audit_id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("quality_rules.id", ondelete="SET NULL"), index=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    affected_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    affected_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DataContractRecord(Base):
    __tablename__ = "data_contracts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(800))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    contract_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    source_audit_id: Mapped[str | None] = mapped_column(ForeignKey("audits.audit_id", ondelete="SET NULL"))
    validation_status: Mapped[str] = mapped_column(String(24), nullable=False, default="not_validated")
    validation_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditScheduleRecord(Base):
    __tablename__ = "audit_schedules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    frequency: Mapped[str] = mapped_column(String(24), nullable=False, default="daily")
    hour: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timezone_offset_minutes: Mapped[int | None] = mapped_column(Integer)
    day_of_week: Mapped[int | None] = mapped_column(Integer)
    day_of_month: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(24))
    last_audit_id: Mapped[str | None] = mapped_column(ForeignKey("audits.audit_id", ondelete="SET NULL"))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class ScheduledAuditRunRecord(Base):
    __tablename__ = "scheduled_audit_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("audit_schedules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    audit_id: Mapped[str | None] = mapped_column(ForeignKey("audits.audit_id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    triggered_by: Mapped[str] = mapped_column(String(32), nullable=False, default="schedule")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[int | None] = mapped_column(Integer)
    issue_count: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    background_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("background_jobs.id", ondelete="SET NULL"), index=True
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AlertRecord(Base):
    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("workspace_id", "fingerprint", name="uq_alert_workspace_fingerprint"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fingerprint: Mapped[str] = mapped_column(String(160), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="new", index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    potential_impact: Mapped[str | None] = mapped_column(Text)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"), index=True)
    dataset_name: Mapped[str | None] = mapped_column(String(255))
    audit_id: Mapped[str | None] = mapped_column(ForeignKey("audits.audit_id", ondelete="SET NULL"), index=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("quality_rules.id", ondelete="SET NULL"), index=True)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("data_contracts.id", ondelete="SET NULL"), index=True)
    reference_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NotificationPreferenceRecord(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_notification_pref_workspace_user"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    in_app_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    email_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    critical_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    high_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    medium_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    low_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConnectorRecord(Base):
    __tablename__ = "connectors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    host_project: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="inactive", index=True)
    configuration_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    credential_hint: Mapped[str | None] = mapped_column(String(255))
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str | None] = mapped_column(String(24))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConnectorSyncRecord(Base):
    __tablename__ = "connector_syncs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("connectors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    discovered_sources: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CopilotSessionRecord(Base):
    __tablename__ = "copilot_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"), index=True)
    audit_id: Mapped[str | None] = mapped_column(ForeignKey("audits.audit_id", ondelete="SET NULL"), index=True)
    compare_audit_id: Mapped[str | None] = mapped_column(ForeignKey("audits.audit_id", ondelete="SET NULL"), index=True)
    analysis_mode: Mapped[str] = mapped_column(String(40), nullable=False, default="general")
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New Copilot session")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class CopilotMessageRecord(Base):
    __tablename__ = "copilot_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("copilot_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class ActionPointRecord(Base):
    __tablename__ = "action_points"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"), index=True)
    audit_id: Mapped[str | None] = mapped_column(ForeignKey("audits.audit_id", ondelete="SET NULL"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("copilot_sessions.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open", index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReportRecord(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(12), nullable=False, default="pdf")
    filters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="completed")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class ReportScheduleRecord(Base):
    __tablename__ = "report_schedules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    frequency: Mapped[str] = mapped_column(String(24), nullable=False, default="weekly")
    format: Mapped[str] = mapped_column(String(12), nullable=False, default="pdf")
    filters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BackgroundJobRecord(Base):
    __tablename__ = "background_jobs"
    __table_args__ = (UniqueConstraint("workspace_id", "idempotency_key", name="uq_background_job_idempotency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    job_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result_json: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OperationalAlertRecord(Base):
    __tablename__ = "operational_alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
