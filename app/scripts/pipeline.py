import argparse
import asyncio

from sqlalchemy import select

from app.collectors.content_extractor import extract_content
from app.analytics.trends import calculate_trend_score
from app.collectors.apify_tiktok import collect_tiktok
from app.database import SessionLocal
from app.models.content_db import ContentItemDB
from app.normalizers.tiktok import normalize_tiktok
from app.repositories.content import save_content


TOP_N = 10
HASHTAG = "nutrition"


async def collect_and_save():
    videos = await collect_tiktok(HASHTAG)
    saved = 0

    with SessionLocal() as session:
        for video in videos:
            extracted_content = await extract_content(video)

            content = normalize_tiktok(
                video,
                transcript=extracted_content,
            )

            before = session.scalar(
                select(ContentItemDB).where(
                    ContentItemDB.external_id == content.external_id
                )
            )

            save_content(session, content)

            if before is None:
                saved += 1

    return len(videos), saved


def calculate_scores():
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

        return len(items)


def get_top_trends():
    with SessionLocal() as session:
        return session.scalars(
            select(ContentItemDB)
            .where(ContentItemDB.trend_score.is_not(None))
            .order_by(ContentItemDB.trend_score.desc())
            .limit(TOP_N)
        ).all()


async def main(collect: bool):

    if collect:
        print("Collecting TikTok data...")

        total, saved = await collect_and_save()

        print(f"Collected: {total}")
        print(f"New records: {saved}")
        print()
    else:
        print("Skipping data collection.")
        print()

    total_scored = calculate_scores()

    print(f"Scored: {total_scored}")
    print()
    print("TOP TRENDS")
    print("-" * 100)

    top_items = get_top_trends()

    for rank, item in enumerate(top_items, start=1):
        print(
            f"{rank:>2}. "
            f"{item.trend_score:8.4f} | "
            f"{item.views:>10,} views | "
            f"{item.author:<25} | "
            f"{item.url}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--collect",
        action="store_true",
        help="Collect fresh TikTok data from Apify",
    )

    args = parser.parse_args()

    asyncio.run(main(args.collect))
