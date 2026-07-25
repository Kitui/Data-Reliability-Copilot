"""connectors

Revision ID: 0012
Revises: 0011
"""
from alembic import op
import sqlalchemy as sa
revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("connectors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("host_project", sa.String(500), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="inactive"),
        sa.Column("configuration_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("credential_hint", sa.String(255)),
        sa.Column("last_tested_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_status", sa.String(24)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_connectors_workspace_id", "connectors", ["workspace_id"])
    op.create_index("ix_connectors_source_type", "connectors", ["source_type"])
    op.create_index("ix_connectors_status", "connectors", ["status"])
    op.create_table("connector_syncs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("connector_id", sa.Integer(), sa.ForeignKey("connectors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("discovered_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_connector_syncs_connector_id", "connector_syncs", ["connector_id"])
    op.create_index("ix_connector_syncs_workspace_id", "connector_syncs", ["workspace_id"])
    op.create_index("ix_connector_syncs_status", "connector_syncs", ["status"])

def downgrade():
    op.drop_table("connector_syncs")
    op.drop_table("connectors")
