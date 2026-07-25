"""Create audit persistence tables.

Revision ID: 0001
Revises:
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audits",
        sa.Column("audit_id", sa.String(length=64), primary_key=True),
        sa.Column("dataset_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("issue_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary_source", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("dataset_name", "created_at", "score", "risk_level"):
        op.create_index(f"ix_audits_{column}", "audits", [column])
    op.create_table(
        "audit_issues",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("audit_id", sa.String(length=64), sa.ForeignKey("audits.audit_id", ondelete="CASCADE"), nullable=False),
        sa.Column("issue_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("affected_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("affected_rate", sa.Float(), nullable=False, server_default="0"),
    )
    for column in ("audit_id", "issue_id", "category", "severity", "status"):
        op.create_index(f"ix_audit_issues_{column}", "audit_issues", [column])
    op.create_table(
        "uploads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("audit_id", sa.String(length=64), sa.ForeignKey("audits.audit_id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False, unique=True),
        sa.Column("relative_path", sa.String(length=500), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_uploads_audit_id", "uploads", ["audit_id"], unique=True)


def downgrade() -> None:
    op.drop_table("uploads")
    op.drop_table("audit_issues")
    op.drop_table("audits")
