"""operational reliability

Revision ID: 0019_operational_reliability
Revises: 0018_security_hardening
"""
from alembic import op
import sqlalchemy as sa

revision = "0019_operational_reliability"
down_revision = "0018_security_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operational_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_operational_alerts_type", "operational_alerts", ["alert_type"])
    op.create_index("ix_operational_alerts_status", "operational_alerts", ["status"])
    op.create_index("ix_operational_alerts_created", "operational_alerts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_operational_alerts_created", table_name="operational_alerts")
    op.drop_index("ix_operational_alerts_status", table_name="operational_alerts")
    op.drop_index("ix_operational_alerts_type", table_name="operational_alerts")
    op.drop_table("operational_alerts")
