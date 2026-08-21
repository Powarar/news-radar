"""add notifications_enabled to users

Revision ID: f1a2b3c4d5e6
Revises: e7a1b2c3d4f5
Create Date: 2026-05-24
"""
import sqlalchemy as sa

from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e7a1b2c3d4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column(
        "notifications_enabled", sa.Boolean(), nullable=False, server_default="false"
    ))


def downgrade() -> None:
    op.drop_column("users", "notifications_enabled")
