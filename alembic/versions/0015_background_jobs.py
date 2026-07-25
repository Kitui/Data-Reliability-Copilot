"""background job foundation

Revision ID: 0015
Revises: 0014
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("job_type", sa.String(48), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("result_json", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("workspace_id", "idempotency_key", name="uq_background_job_idempotency"),
    )
    op.create_index("ix_background_jobs_workspace_id", "background_jobs", ["workspace_id"])
    op.create_index("ix_background_jobs_created_by_user_id", "background_jobs", ["created_by_user_id"])
    op.create_index("ix_background_jobs_job_type", "background_jobs", ["job_type"])
    op.create_index("ix_background_jobs_status", "background_jobs", ["status"])
    op.create_index("ix_background_jobs_created_at", "background_jobs", ["created_at"])


def downgrade():
    op.drop_index("ix_background_jobs_created_at", table_name="background_jobs")
    op.drop_index("ix_background_jobs_status", table_name="background_jobs")
    op.drop_index("ix_background_jobs_job_type", table_name="background_jobs")
    op.drop_index("ix_background_jobs_created_by_user_id", table_name="background_jobs")
    op.drop_index("ix_background_jobs_workspace_id", table_name="background_jobs")
    op.drop_table("background_jobs")
