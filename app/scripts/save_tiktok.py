import asyncio
import os
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
from app.collectors.apify_tiktok import collect_tiktok
from app.normalizers.tiktok import normalize_tiktok
from app.database import SessionLocal
from app.repositories.content import save_content


async def main():
    videos = await collect_tiktok("nutrition")

    with SessionLocal() as session:
        for video in videos:
            content = normalize_tiktok(video)
            save_content(session, content)

    print(f"Saved {len(videos)} videos")


if __name__ == "__main__":
    asyncio.run(main())
