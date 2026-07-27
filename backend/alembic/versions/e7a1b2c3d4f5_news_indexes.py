"""add indexes on news_items.published_at and news_items.language

Revision ID: e7a1b2c3d4f5
Revises: edd510d0335a
Create Date: 2026-05-16 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = 'e7a1b2c3d4f5'
down_revision: str | None = 'edd510d0335a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(op.f('ix_news_items_language'), 'news_items', ['language'])
    op.create_index(op.f('ix_news_items_published_at'), 'news_items', ['published_at'])


def downgrade() -> None:
    op.drop_index(op.f('ix_news_items_published_at'), table_name='news_items')
    op.drop_index(op.f('ix_news_items_language'), table_name='news_items')
