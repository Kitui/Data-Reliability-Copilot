"""dataset registry

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(120), nullable=False, server_default="General"),
        sa.Column("owner_name", sa.String(255), nullable=False, server_default="Unassigned"),
        sa.Column("environment", sa.String(32), nullable=False, server_default="production"),
        sa.Column("status", sa.String(32), nullable=False, server_default="registered"),
        sa.Column("source_type", sa.String(64), nullable=False, server_default="CSV"),
        sa.Column("description", sa.String(800), nullable=True),
        sa.Column("labels_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("column_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("issue_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latest_audit_id", sa.String(64), sa.ForeignKey("audits.audit_id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "name", name="uq_datasets_workspace_name"),
    )
    op.create_index("ix_datasets_workspace_id", "datasets", ["workspace_id"])
    op.create_index("ix_datasets_name", "datasets", ["name"])
    op.create_index("ix_datasets_status", "datasets", ["status"])
    op.execute("""
        INSERT INTO datasets (workspace_id, name, domain, owner_name, environment, status, source_type,
          labels_json, record_count, column_count, quality_score, issue_count, latest_audit_id, created_at, updated_at)
        SELECT a.workspace_id, a.dataset_name, 'General', 'Workspace team', 'production',
          CASE WHEN a.score >= 80 THEN 'healthy' WHEN a.score >= 60 THEN 'warning' ELSE 'review_needed' END,
          'CSV', '[]', 0, 0, a.score, a.issue_count, a.audit_id, a.created_at, a.updated_at
        FROM audits a
        JOIN (
          SELECT workspace_id, dataset_name, MAX(created_at) AS latest_created
          FROM audits WHERE workspace_id IS NOT NULL GROUP BY workspace_id, dataset_name
        ) latest ON latest.workspace_id = a.workspace_id AND latest.dataset_name = a.dataset_name AND latest.latest_created = a.created_at
    """)


def downgrade():
    op.drop_index("ix_datasets_status", table_name="datasets")
    op.drop_index("ix_datasets_name", table_name="datasets")
    op.drop_index("ix_datasets_workspace_id", table_name="datasets")
    op.drop_table("datasets")
