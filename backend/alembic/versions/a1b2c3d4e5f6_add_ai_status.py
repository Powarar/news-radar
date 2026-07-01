"""add ai_status to news_items

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("news_items", sa.Column(
        "ai_status", sa.String(length=20), nullable=True
    ))


def downgrade() -> None:
    op.drop_column("news_items", "ai_status")
