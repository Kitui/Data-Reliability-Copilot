"""contracts workspace completion

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "data_contracts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contract_key", sa.String(64), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(800)),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("contract_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("source_audit_id", sa.String(64), sa.ForeignKey("audits.audit_id", ondelete="SET NULL")),
        sa.Column("validation_status", sa.String(24), nullable=False, server_default="not_validated"),
        sa.Column("validation_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("validated_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_data_contracts_contract_key", "data_contracts", ["contract_key"])
    op.create_index("ix_data_contracts_workspace_id", "data_contracts", ["workspace_id"])
    op.create_index("ix_data_contracts_dataset_id", "data_contracts", ["dataset_id"])
    op.create_index("ix_data_contracts_status", "data_contracts", ["status"])

def downgrade():
    op.drop_table("data_contracts")
