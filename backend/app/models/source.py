from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SourceType(str, Enum):
    telegram = "telegram"
    website = "website"
    rss = "rss"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(512), unique=True)
    type: Mapped[SourceType] = mapped_column(String(20))
    language: Mapped[str] = mapped_column(String(10), default="en")
    country: Mapped[str | None] = mapped_column(String(10))
    topics: Mapped[str | None] = mapped_column(Text)  # JSON list: ["politics","tech"]

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    fetch_interval_minutes: Mapped[int] = mapped_column(Integer, default=15)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    news_items: Mapped[list["NewsItem"]] = relationship(back_populates="source")
