"""scheduled audits and monitoring

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("audit_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("frequency", sa.String(24), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("minute", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.Integer()),
        sa.Column("day_of_month", sa.Integer()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_status", sa.String(24)),
        sa.Column("last_audit_id", sa.String(64), sa.ForeignKey("audits.audit_id", ondelete="SET NULL")),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_schedules_workspace_id", "audit_schedules", ["workspace_id"])
    op.create_index("ix_audit_schedules_dataset_id", "audit_schedules", ["dataset_id"])
    op.create_index("ix_audit_schedules_status", "audit_schedules", ["status"])
    op.create_index("ix_audit_schedules_next_run_at", "audit_schedules", ["next_run_at"])
    op.create_table("scheduled_audit_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("audit_schedules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("audit_id", sa.String(64), sa.ForeignKey("audits.audit_id", ondelete="SET NULL")),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("triggered_by", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("score", sa.Integer()),
        sa.Column("issue_count", sa.Integer()),
        sa.Column("error_message", sa.Text()),
    )
    for name, cols in [("ix_scheduled_audit_runs_schedule_id", ["schedule_id"]),("ix_scheduled_audit_runs_workspace_id", ["workspace_id"]),("ix_scheduled_audit_runs_dataset_id", ["dataset_id"]),("ix_scheduled_audit_runs_audit_id", ["audit_id"]),("ix_scheduled_audit_runs_status", ["status"]),("ix_scheduled_audit_runs_started_at", ["started_at"])]:
        op.create_index(name, "scheduled_audit_runs", cols)

def downgrade():
    op.drop_table("scheduled_audit_runs")
    op.drop_table("audit_schedules")
