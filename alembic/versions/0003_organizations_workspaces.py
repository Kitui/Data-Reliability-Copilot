"""Add organizations, workspaces, memberships, and audit scoping.

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "slug", name="uq_workspaces_org_slug"),
    )
    op.create_index("ix_workspaces_organization_id", "workspaces", ["organization_id"])
    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
    )
    op.create_index("ix_memberships_user_id", "organization_memberships", ["user_id"])
    with op.batch_alter_table("user_sessions") as batch:
        batch.add_column(sa.Column("active_workspace_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_sessions_active_workspace", "workspaces", ["active_workspace_id"], ["id"], ondelete="SET NULL")
    with op.batch_alter_table("audits") as batch:
        batch.add_column(sa.Column("workspace_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_audits_workspace", "workspaces", ["workspace_id"], ["id"], ondelete="CASCADE")
        batch.create_index("ix_audits_workspace_id", ["workspace_id"])


def downgrade() -> None:
    with op.batch_alter_table("audits") as batch:
        batch.drop_index("ix_audits_workspace_id")
        batch.drop_constraint("fk_audits_workspace", type_="foreignkey")
        batch.drop_column("workspace_id")
    with op.batch_alter_table("user_sessions") as batch:
        batch.drop_constraint("fk_sessions_active_workspace", type_="foreignkey")
        batch.drop_column("active_workspace_id")
    op.drop_table("organization_memberships")
    op.drop_table("workspaces")
    op.drop_table("organizations")
