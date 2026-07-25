"""Phase 2 security hardening.

Revision ID: 0018_security_hardening
Revises: 0017
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_security_hardening"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_locked_until", "users", ["locked_until"])
    op.add_column("user_sessions", sa.Column("ip_address", sa.String(length=64), nullable=True))
    op.add_column("user_sessions", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_user_sessions_revoked_at", "user_sessions", ["revoked_at"])
    op.create_table("login_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.String(500)),
    )
    op.create_index("ix_login_attempts_email", "login_attempts", ["email"])
    op.create_index("ix_login_attempts_ip_address", "login_attempts", ["ip_address"])
    op.create_index("ix_login_attempts_attempted_at", "login_attempts", ["attempted_at"])
    op.create_table("account_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_account_tokens_user_id", "account_tokens", ["user_id"])
    op.create_index("ix_account_tokens_purpose", "account_tokens", ["purpose"])
    op.create_index("ix_account_tokens_expires_at", "account_tokens", ["expires_at"])
    op.create_table("administrative_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="SET NULL")),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="SET NULL")),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(80)),
        sa.Column("resource_id", sa.String(120)),
        sa.Column("outcome", sa.String(24), nullable=False, server_default="success"),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name, cols in [("workspace_id", ["workspace_id"]), ("organization_id", ["organization_id"]), ("actor_user_id", ["actor_user_id"]), ("action", ["action"]), ("resource_type", ["resource_type"]), ("outcome", ["outcome"]), ("created_at", ["created_at"])]:
        op.create_index(f"ix_administrative_audit_log_{name}", "administrative_audit_log", cols)


def downgrade():
    op.drop_table("administrative_audit_log")
    op.drop_table("account_tokens")
    op.drop_table("login_attempts")
    op.drop_index("ix_user_sessions_revoked_at", table_name="user_sessions")
    op.drop_column("user_sessions", "revoked_at")
    op.drop_column("user_sessions", "ip_address")
    op.drop_index("ix_users_locked_until", table_name="users")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "email_verified_at")
