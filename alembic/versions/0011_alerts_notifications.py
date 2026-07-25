"""alerts and notifications

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fingerprint", sa.String(160), nullable=False),
        sa.Column("alert_type", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="new"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("potential_impact", sa.Text()),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="SET NULL")),
        sa.Column("dataset_name", sa.String(255)),
        sa.Column("audit_id", sa.String(64), sa.ForeignKey("audits.audit_id", ondelete="SET NULL")),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("quality_rules.id", ondelete="SET NULL")),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("data_contracts.id", ondelete="SET NULL")),
        sa.Column("reference_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("dismissed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "fingerprint", name="uq_alert_workspace_fingerprint"),
    )
    op.create_index("ix_alerts_workspace_status", "alerts", ["workspace_id", "status"])
    op.create_index("ix_alerts_workspace_severity", "alerts", ["workspace_id", "severity"])
    op.create_table("notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("in_app_enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("email_enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("critical_enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("high_enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("medium_enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("low_enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score_threshold", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_notification_pref_workspace_user"),
    )

def downgrade():
    op.drop_table("notification_preferences")
    op.drop_index("ix_alerts_workspace_severity", table_name="alerts")
    op.drop_index("ix_alerts_workspace_status", table_name="alerts")
    op.drop_table("alerts")
