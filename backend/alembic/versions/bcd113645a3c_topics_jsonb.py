"""topics_jsonb

Revision ID: bcd113645a3c
Revises: a1b2c3d4e5f6
Create Date: 2026-07-02 20:26:13.581808

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'bcd113645a3c'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE news_items ALTER COLUMN topics TYPE jsonb USING topics::jsonb")


def downgrade() -> None:
    op.alter_column('news_items', 'topics',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               type_=sa.TEXT(),
               existing_nullable=True)
