from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import ContentItem
from app.models.content_db import ContentItemDB


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
