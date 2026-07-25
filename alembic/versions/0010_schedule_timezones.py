"""schedule timezone support

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("audit_schedules", sa.Column("timezone_offset_minutes", sa.Integer(), nullable=True))

def downgrade():
    op.drop_column("audit_schedules", "timezone_offset_minutes")
