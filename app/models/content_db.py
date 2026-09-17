from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ContentItemDB(Base):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(50))
    external_id: Mapped[str] = mapped_column(String(255), unique=True)
    author: Mapped[str] = mapped_column(String(255))

    text: Mapped[str]
    transcript: Mapped[str | None]

    views: Mapped[int]
    likes: Mapped[int]
    comments: Mapped[int]
    shares: Mapped[int]
    url: Mapped[str]
    created_at: Mapped[str]
    trend_score: Mapped[float | None]


class TelegramUserSettingsDB(Base):
    """Постоянные настройки одного пользователя Telegram."""

    __tablename__ = "telegram_user_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(unique=True, index=True)
    profiles: Mapped[list[str]] = mapped_column(JSON, default=list)
    hashtags: Mapped[list[str]] = mapped_column(JSON, default=list)
    results_count: Mapped[int] = mapped_column(default=5)
    min_video_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    idea_prompt: Mapped[str | None] = mapped_column(nullable=True)
    post_prompt: Mapped[str | None] = mapped_column(nullable=True)
    allow_reparse_used_videos: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class UsedTikTokVideoDB(Base):
    """Ролик, по которому пользователь уже создал Telegram-пост."""

    __tablename__ = "used_tiktok_videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(index=True)
    content_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_items.id"),
        nullable=True,
    )
    tiktok_video_id: Mapped[str] = mapped_column(String(255))
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1_000), nullable=True)
    used_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
