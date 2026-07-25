"""reliability copilot

Revision ID: 0013
Revises: 0012
"""
from alembic import op
import sqlalchemy as sa
revision="0013"
down_revision="0012"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("copilot_sessions",
        sa.Column("id",sa.Integer(),primary_key=True,autoincrement=True),
        sa.Column("workspace_id",sa.Integer(),sa.ForeignKey("workspaces.id",ondelete="CASCADE"),nullable=False),
        sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),
        sa.Column("dataset_id",sa.Integer(),sa.ForeignKey("datasets.id",ondelete="SET NULL")),
        sa.Column("audit_id",sa.String(64),sa.ForeignKey("audits.audit_id",ondelete="SET NULL")),
        sa.Column("compare_audit_id",sa.String(64),sa.ForeignKey("audits.audit_id",ondelete="SET NULL")),
        sa.Column("analysis_mode",sa.String(40),nullable=False,server_default="general"),
        sa.Column("title",sa.String(255),nullable=False,server_default="New Copilot session"),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    for col in ("workspace_id","user_id","dataset_id","audit_id","compare_audit_id","updated_at"): op.create_index(f"ix_copilot_sessions_{col}","copilot_sessions",[col])
    op.create_table("copilot_messages",
        sa.Column("id",sa.Integer(),primary_key=True,autoincrement=True),
        sa.Column("session_id",sa.Integer(),sa.ForeignKey("copilot_sessions.id",ondelete="CASCADE"),nullable=False),
        sa.Column("workspace_id",sa.Integer(),sa.ForeignKey("workspaces.id",ondelete="CASCADE"),nullable=False),
        sa.Column("role",sa.String(16),nullable=False),sa.Column("content",sa.Text(),nullable=False),
        sa.Column("evidence_json",sa.Text(),nullable=False,server_default="{}"),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    for col in ("session_id","workspace_id","created_at"): op.create_index(f"ix_copilot_messages_{col}","copilot_messages",[col])
    op.create_table("action_points",
        sa.Column("id",sa.Integer(),primary_key=True,autoincrement=True),sa.Column("workspace_id",sa.Integer(),sa.ForeignKey("workspaces.id",ondelete="CASCADE"),nullable=False),
        sa.Column("dataset_id",sa.Integer(),sa.ForeignKey("datasets.id",ondelete="SET NULL")),sa.Column("audit_id",sa.String(64),sa.ForeignKey("audits.audit_id",ondelete="SET NULL")),
        sa.Column("session_id",sa.Integer(),sa.ForeignKey("copilot_sessions.id",ondelete="SET NULL")),sa.Column("title",sa.String(255),nullable=False),
        sa.Column("description",sa.Text(),nullable=False),sa.Column("priority",sa.String(16),nullable=False,server_default="medium"),
        sa.Column("status",sa.String(24),nullable=False,server_default="open"),sa.Column("created_by_user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="SET NULL")),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    for col in ("workspace_id","dataset_id","audit_id","session_id","status"): op.create_index(f"ix_action_points_{col}","action_points",[col])

def downgrade():
    op.drop_table("action_points");op.drop_table("copilot_messages");op.drop_table("copilot_sessions")
