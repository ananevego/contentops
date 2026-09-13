from sqlalchemy import select

from app.database import SessionLocal
from app.models.content_db import ContentItemDB


with SessionLocal() as session:
    items = session.scalars(
        select(ContentItemDB)
        .where(ContentItemDB.trend_score.is_not(None))
        .order_by(ContentItemDB.trend_score.desc())
        .limit(10)
    ).all()


for rank, item in enumerate(items, start=1):
    print(
        f"{rank:>2}. "
        f"{item.trend_score:8.4f} | "
        f"{item.views:>10,} views | "
        f"{item.author:<25} | "
        f"{item.url}"
    )
