"""reports and report schedules

Revision ID: 0014
Revises: 0013
"""
from alembic import op
import sqlalchemy as sa
revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("reports",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("workspace_id",sa.Integer(),sa.ForeignKey("workspaces.id",ondelete="CASCADE"),nullable=False),
        sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="SET NULL")),
        sa.Column("name",sa.String(255),nullable=False),sa.Column("report_type",sa.String(64),nullable=False),
        sa.Column("format",sa.String(12),nullable=False,server_default="pdf"),sa.Column("filters_json",sa.Text(),nullable=False,server_default="{}"),
        sa.Column("status",sa.String(24),nullable=False,server_default="completed"),sa.Column("generated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_reports_workspace_id","reports",["workspace_id"])
    op.create_index("ix_reports_report_type","reports",["report_type"])
    op.create_index("ix_reports_generated_at","reports",["generated_at"])
    op.create_table("report_schedules",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("workspace_id",sa.Integer(),sa.ForeignKey("workspaces.id",ondelete="CASCADE"),nullable=False),
        sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("name",sa.String(255),nullable=False),
        sa.Column("report_type",sa.String(64),nullable=False),sa.Column("frequency",sa.String(24),nullable=False,server_default="weekly"),
        sa.Column("format",sa.String(12),nullable=False,server_default="pdf"),sa.Column("filters_json",sa.Text(),nullable=False,server_default="{}"),
        sa.Column("is_active",sa.Integer(),nullable=False,server_default="1"),sa.Column("next_run_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_report_schedules_workspace_id","report_schedules",["workspace_id"])
    op.create_index("ix_report_schedules_next_run_at","report_schedules",["next_run_at"])

def downgrade():
    op.drop_table("report_schedules")
    op.drop_table("reports")
