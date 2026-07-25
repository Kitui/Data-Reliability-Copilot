"""dedicated scheduling and job dispatch

Revision ID: 0017
Revises: 0016
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("audit_schedules") as batch:
        batch.add_column(sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_audit_schedules_claimed_at", ["claimed_at"])
    with op.batch_alter_table("scheduled_audit_runs") as batch:
        batch.add_column(sa.Column("background_job_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key(
            "fk_scheduled_audit_runs_background_job_id",
            "background_jobs",
            ["background_job_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_scheduled_audit_runs_background_job_id", ["background_job_id"])
        batch.create_index("ix_scheduled_audit_runs_scheduled_for", ["scheduled_for"])


def downgrade():
    with op.batch_alter_table("scheduled_audit_runs") as batch:
        batch.drop_index("ix_scheduled_audit_runs_scheduled_for")
        batch.drop_index("ix_scheduled_audit_runs_background_job_id")
        batch.drop_constraint("fk_scheduled_audit_runs_background_job_id", type_="foreignkey")
        batch.drop_column("scheduled_for")
        batch.drop_column("background_job_id")
    with op.batch_alter_table("audit_schedules") as batch:
        batch.drop_index("ix_audit_schedules_claimed_at")
        batch.drop_column("claimed_at")
