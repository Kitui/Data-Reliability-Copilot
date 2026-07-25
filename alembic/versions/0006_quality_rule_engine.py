"""quality rule engine

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("quality_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(800)),
        sa.Column("rule_type", sa.String(40), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False, server_default="column"),
        sa.Column("column_name", sa.String(255)),
        sa.Column("category", sa.String(32), nullable=False, server_default="validity"),
        sa.Column("severity", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("parameters_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("recommendation", sa.String(1000)),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_quality_rules_workspace_id", "quality_rules", ["workspace_id"])
    op.create_index("ix_quality_rules_rule_type", "quality_rules", ["rule_type"])
    op.create_index("ix_quality_rules_is_active", "quality_rules", ["is_active"])
    op.create_table("dataset_rule_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("quality_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dataset_id", "rule_id", name="uq_dataset_rule_assignment"),
    )
    op.create_index("ix_dataset_rule_assignments_dataset_id", "dataset_rule_assignments", ["dataset_id"])
    op.create_index("ix_dataset_rule_assignments_rule_id", "dataset_rule_assignments", ["rule_id"])
    op.create_table("rule_executions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("audit_id", sa.String(64), sa.ForeignKey("audits.audit_id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("quality_rules.id", ondelete="SET NULL")),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("affected_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("affected_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rule_executions_audit_id", "rule_executions", ["audit_id"])
    op.create_index("ix_rule_executions_rule_id", "rule_executions", ["rule_id"])
    op.create_index("ix_rule_executions_outcome", "rule_executions", ["outcome"])


def downgrade():
    op.drop_table("rule_executions")
    op.drop_table("dataset_rule_assignments")
    op.drop_table("quality_rules")
