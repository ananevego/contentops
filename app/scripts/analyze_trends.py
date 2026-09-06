from sqlalchemy import select

from app.database import SessionLocal
from app.models.content_db import ContentItemDB
from app.analytics.trends import calculate_trend_score


with SessionLocal() as session:
    items = session.scalars(
        select(ContentItemDB)
    ).all()

    results = []

    for item in items:
        score = calculate_trend_score(
            views=item.views,
            likes=item.likes,
            comments=item.comments,
            shares=item.shares,
            created_at=item.created_at,
        )

        results.append((score, item))

results.sort(reverse=True, key=lambda x: x[0])

for score, item in results:
    print(
        f"{score:8.4f} | "
        f"{item.views:>10,} views | "
        f"{item.author:<25} | "
        f"{item.url}"
    )
