from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.content import ContentItem
from app.api.schemas import normalize_tag_names
from app.models.content_db import ContentCategoryDB, ContentItemDB, TagDB


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
    tags: list[str] | None = None,
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
    if tags:
        item.tags = _get_or_create_tags(session, tags)
    session.commit()
    session.refresh(item)
    return item


def _get_or_create_tags(session: Session, tag_names: list[str]) -> list[TagDB]:
    normalized = normalize_tag_names(tag_names)
    existing = {
        tag.name: tag
        for tag in session.scalars(select(TagDB).where(TagDB.name.in_(normalized)))
    }
    tags: list[TagDB] = []
    for name in normalized:
        tag = existing.get(name)
        if tag is None:
            tag = TagDB(name=name)
            session.add(tag)
        tags.append(tag)
    session.flush()
    return tags


def update_content(
    session: Session,
    item: ContentItemDB,
    changes: dict,
    *,
    tags: list[str] | None = None,
) -> ContentItemDB:
    """Applies explicit API fields only; it never evaluates dynamic attributes."""
    allowed = {
        "source", "author", "text", "transcript", "views", "likes",
        "comments", "shares", "url", "created_at", "trend_score",
    }
    for field, value in changes.items():
        if field in allowed:
            setattr(item, field, value)
    if tags is not None:
        item.tags = _get_or_create_tags(session, tags)
    session.commit()
    session.refresh(item)
    return item


def delete_content(session: Session, item: ContentItemDB) -> None:
    """Deletes a content item while preserving historical used-video rows."""
    for used_record in item.used_records:
        used_record.content_id = None
    session.delete(item)
    session.commit()


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
