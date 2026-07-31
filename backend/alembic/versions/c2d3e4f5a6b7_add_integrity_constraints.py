"""add integrity constraints and feed indexes

Revision ID: c2d3e4f5a6b7
Revises: bcd113645a3c
Create Date: 2026-07-27
"""

from alembic import op

revision = "c2d3e4f5a6b7"
down_revision = "bcd113645a3c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep the newest row if historical application races created duplicates.
    op.execute(
        """
        DELETE FROM news_reactions older
        USING news_reactions newer
        WHERE older.user_id = newer.user_id
          AND older.news_item_id = newer.news_item_id
          AND older.id < newer.id
        """
    )
    op.execute(
        """
        DELETE FROM user_topic_preferences older
        USING user_topic_preferences newer
        WHERE older.user_id = newer.user_id
          AND older.topic = newer.topic
          AND older.id < newer.id
        """
    )
    op.execute(
        """
        DELETE FROM user_source_settings older
        USING user_source_settings newer
        WHERE older.user_id = newer.user_id
          AND older.source_id = newer.source_id
          AND older.id < newer.id
        """
    )

    op.create_unique_constraint(
        "uq_news_reactions_user_news",
        "news_reactions",
        ["user_id", "news_item_id"],
    )
    op.create_unique_constraint(
        "uq_user_topic_preferences_user_topic",
        "user_topic_preferences",
        ["user_id", "topic"],
    )
    op.create_unique_constraint(
        "uq_user_source_settings_user_source",
        "user_source_settings",
        ["user_id", "source_id"],
    )
    op.create_index("ix_news_items_source_id", "news_items", ["source_id"])
    op.create_index(
        "ix_news_items_topics_gin",
        "news_items",
        ["topics"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_news_items_topics_gin", table_name="news_items")
    op.drop_index("ix_news_items_source_id", table_name="news_items")
    op.drop_constraint(
        "uq_user_source_settings_user_source",
        "user_source_settings",
        type_="unique",
    )
    op.drop_constraint(
        "uq_user_topic_preferences_user_topic",
        "user_topic_preferences",
        type_="unique",
    )
    op.drop_constraint(
        "uq_news_reactions_user_news",
        "news_reactions",
        type_="unique",
    )
