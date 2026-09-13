from sqlalchemy import select

from app.analytics.trends import calculate_trend_score
from app.database import SessionLocal
from app.models.content_db import ContentItemDB


with SessionLocal() as session:
    items = session.scalars(
        select(ContentItemDB)
    ).all()

    for item in items:
        item.trend_score = calculate_trend_score(
            views=item.views,
            likes=item.likes,
            comments=item.comments,
            shares=item.shares,
            created_at=item.created_at,
        )

    session.commit()

print(f"Updated trend scores for {len(items)} items")
