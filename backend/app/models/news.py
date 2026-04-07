from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ReactionType(str, Enum):
    like = "like"
    dislike = "dislike"
    blacklist = "blacklist"


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))

    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)       # HF summarization
    url: Mapped[str | None] = mapped_column(String(512), unique=True)
    image_url: Mapped[str | None] = mapped_column(String(512))

    language: Mapped[str] = mapped_column(String(10), default="en")
    topics: Mapped[str | None] = mapped_column(Text)         # JSON: {"politics": 0.9, "tech": 0.2}
    importance_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 – 1.0

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    source: Mapped["Source"] = relationship(back_populates="news_items")
    reactions: Mapped[list["NewsReaction"]] = relationship(back_populates="news_item", cascade="all, delete")


class NewsReaction(Base):
    __tablename__ = "news_reactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    news_item_id: Mapped[int] = mapped_column(ForeignKey("news_items.id"))
    reaction: Mapped[ReactionType] = mapped_column(String(20))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="reactions")
    news_item: Mapped["NewsItem"] = relationship(back_populates="reactions")
