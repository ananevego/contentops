from sqlalchemy import String, Integer
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
