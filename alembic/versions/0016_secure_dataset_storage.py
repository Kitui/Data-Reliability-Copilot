q"""secure dataset storage metadata

Revision ID: 0016
Revises: 0015
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("uploads", sa.Column("storage_backend", sa.String(24), nullable=False, server_default="local"))
    op.add_column("uploads", sa.Column("checksum_sha256", sa.String(64), nullable=True))
    op.add_column("uploads", sa.Column("display_name", sa.String(255), nullable=True))


def downgrade():
    op.drop_column("uploads", "display_name")
    op.drop_column("uploads", "checksum_sha256")
    op.drop_column("uploads", "storage_backend")
