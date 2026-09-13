from sqlalchemy import select

from app.database import SessionLocal
from app.models.content_db import ContentItemDB
from app.generators.content_ideas import generate_content_idea


with SessionLocal() as session:
    item = session.scalar(
        select(ContentItemDB)
        .where(ContentItemDB.trend_score.is_not(None))
        .order_by(ContentItemDB.trend_score.desc())
    )

    if item is None:
        print("No content found")
    else:
        print(f"Analyzing: {item.author}")
        print(f"URL: {item.url}")
        print()

        result = generate_content_idea(item)

        print(result)
