from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.content_db import Base
from app.repositories.content import create_content, list_content


def test_repository_creates_and_safely_filters_content():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        created = create_content(
            session,
            source="tiktok",
            external_id="repository-1",
            author="demo",
            text="Safe repository test",
            transcript=None,
            views=500,
            likes=80,
            comments=10,
            shares=5,
            url="https://example.com/video",
            created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            trend_score=2.5,
            category="fitness",
        )
        duplicate = create_content(
            session,
            source="tiktok",
            external_id="repository-1",
            author="another",
            text="Ignored duplicate",
            transcript=None,
            views=1,
            likes=0,
            comments=0,
            shares=0,
            url="https://example.com/duplicate",
            created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        )
        items = list_content(
            session,
            platform="tiktok",
            category="fitness",
            min_trend_score=2,
            limit=10,
        )

    assert duplicate.id == created.id
    assert [item.external_id for item in items] == ["repository-1"]
