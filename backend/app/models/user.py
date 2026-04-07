from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserPlan(str, Enum):
    free = "free"
    pro = "pro"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    hashed_password: Mapped[str | None] = mapped_column(Text)  # None for OAuth users
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    telegram_id: Mapped[str | None] = mapped_column(String(64), unique=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    plan: Mapped[UserPlan] = mapped_column(String(20), default=UserPlan.free)
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Localization
    language: Mapped[str] = mapped_column(String(10), default="en")  # en, ru, etc.
    country: Mapped[str | None] = mapped_column(String(10))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relations
    preferences: Mapped[list["UserTopicPreference"]] = relationship(back_populates="user", cascade="all, delete")
    source_settings: Mapped[list["UserSourceSetting"]] = relationship(back_populates="user", cascade="all, delete")
    reactions: Mapped[list["NewsReaction"]] = relationship(back_populates="user", cascade="all, delete")


class UserTopicPreference(Base):
    __tablename__ = "user_topic_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    topic: Mapped[str] = mapped_column(String(50))   # politics, tech, military, health, science, business, sports
    weight: Mapped[float] = mapped_column(default=0.5)  # 0.0 – 1.0

    user: Mapped["User"] = relationship(back_populates="preferences")


class UserSourceSetting(Base):
    __tablename__ = "user_source_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    blacklisted: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="source_settings")
    source: Mapped["Source"] = relationship()
