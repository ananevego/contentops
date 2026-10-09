from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# Association table is deliberately schema-only: a tag may describe many
# content items and every content item may have many tags.
content_item_tags = Table(
    "content_item_tags",
    Base.metadata,
    Column("content_id", ForeignKey("content_items.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


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
    # The foreign key existed before this relationship declaration.  Declaring
    # both sides makes the existing 1:N relation visible to SQLAlchemy without
    # requiring a destructive schema migration.
    used_records: Mapped[list["UsedTikTokVideoDB"]] = relationship(
        back_populates="content_item",
    )
    categories: Mapped[list["ContentCategoryDB"]] = relationship(
        back_populates="content_item",
        cascade="all, delete-orphan",
    )
    tags: Mapped[list["TagDB"]] = relationship(
        secondary=content_item_tags,
        back_populates="content_items",
    )


class TagDB(Base):
    """Reusable tag in the ContentItem ↔ Tag many-to-many relation."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    content_items: Mapped[list[ContentItemDB]] = relationship(
        secondary=content_item_tags,
        back_populates="tags",
    )


class ContentCategoryDB(Base):
    """A normalized 1:N category relation added without changing old content rows."""

    __tablename__ = "content_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id"), index=True)
    name: Mapped[str] = mapped_column(String(50), index=True)
    content_item: Mapped[ContentItemDB] = relationship(back_populates="categories")


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
    content_item: Mapped[ContentItemDB | None] = relationship(
        back_populates="used_records",
    )


class ExcludedTikTokVideoDB(Base):
    """Ролик, который пользователь не хочет видеть в трендах."""

    __tablename__ = "excluded_tiktok_videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(index=True)
    tiktok_video_id: Mapped[str] = mapped_column(String(255))
    excluded_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
