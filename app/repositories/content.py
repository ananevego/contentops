from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.content import ContentItem
from app.models.content_db import ContentCategoryDB, ContentItemDB


def save_content(session: Session, content: ContentItem):
    existing = session.scalar(
        select(ContentItemDB).where(
            ContentItemDB.external_id == content.external_id
        )
    )

    if existing:
        return existing

    db_content = ContentItemDB(
        source=content.source,
        external_id=content.external_id,
        author=content.author,
        text=content.text,
        transcript=content.transcript,
        views=content.views,
        likes=content.likes,
        comments=content.comments,
        shares=content.shares,
        url=content.url,
        created_at=content.created_at,
    )

    session.add(db_content)
    session.commit()
    session.refresh(db_content)

    return db_content


def get_content(session: Session, content_id: int) -> ContentItemDB | None:
    return session.get(ContentItemDB, content_id)


def create_content(
    session: Session,
    *,
    source: str,
    external_id: str,
    author: str,
    text: str,
    transcript: str | None,
    views: int,
    likes: int,
    comments: int,
    shares: int,
    url: str,
    created_at: datetime,
    trend_score: float | None = None,
    category: str | None = None,
) -> ContentItemDB:
    """Creates one API-supplied item, returning an existing external ID safely."""
    existing = session.scalar(
        select(ContentItemDB).where(ContentItemDB.external_id == external_id)
    )
    if existing:
        return existing

    item = ContentItemDB(
        source=source,
        external_id=external_id,
        author=author,
        text=text,
        transcript=transcript,
        views=views,
        likes=likes,
        comments=comments,
        shares=shares,
        url=url,
        created_at=created_at.isoformat(),
        trend_score=trend_score,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    if category:
        session.add(ContentCategoryDB(content_id=item.id, name=category))
        session.commit()
    return item


def list_content(
    session: Session,
    *,
    platform: str | None = None,
    category: str | None = None,
    created_after: datetime | None = None,
    min_trend_score: float | None = None,
    limit: int = 50,
) -> list[ContentItemDB]:
    """Reads content with allow-listed SQL filters; no dynamic SQL is built."""
    statement: Select[tuple[ContentItemDB]] = select(ContentItemDB)
    if platform:
        statement = statement.where(ContentItemDB.source == platform)
    if category:
        statement = statement.join(ContentCategoryDB).where(ContentCategoryDB.name == category)
    if created_after:
        statement = statement.where(ContentItemDB.created_at >= created_after.isoformat())
    if min_trend_score is not None:
        statement = statement.where(ContentItemDB.trend_score >= min_trend_score)

    statement = statement.distinct().order_by(ContentItemDB.trend_score.desc()).limit(min(limit, 100))
    return list(session.scalars(statement))
