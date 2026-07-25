"""issue lifecycle management

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "issue_activities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("audit_id", sa.String(64), sa.ForeignKey("audits.audit_id", ondelete="CASCADE"), nullable=False),
        sa.Column("issue_id", sa.String(64), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("actor_name", sa.String(255)),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("field_name", sa.String(64)),
        sa.Column("previous_value", sa.Text()),
        sa.Column("new_value", sa.Text()),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_issue_activities_audit_id", "issue_activities", ["audit_id"])
    op.create_index("ix_issue_activities_issue_id", "issue_activities", ["issue_id"])
    op.create_index("ix_issue_activities_workspace_id", "issue_activities", ["workspace_id"])
    op.create_index("ix_issue_activities_actor_user_id", "issue_activities", ["actor_user_id"])
    op.create_index("ix_issue_activities_action", "issue_activities", ["action"])
    op.create_index("ix_issue_activities_created_at", "issue_activities", ["created_at"])


def downgrade():
    op.drop_table("issue_activities")
