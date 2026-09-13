import asyncio
import json

from app.collectors.content_extractor import extract_content
from app.database import SessionLocal
from app.models.content import ContentItem
from app.normalizers.tiktok import normalize_tiktok
from app.repositories.content import save_content


FILE_PATH = "app/scripts/tiktok_slideshow.json"


async def main():
    # 1. Загружаем реальный TikTok JSON
    with open(FILE_PATH, "r", encoding="utf-8") as file:
        videos = json.load(file)

    video = videos[0]

    print("VIDEO:")
    print(video["webVideoUrl"])
    print(f"Slideshow: {video['isSlideshow']}")

    # 2. Извлекаем содержимое
    transcript = await extract_content(video)

    print("\nEXTRACTED:")
    print(transcript[:500] if transcript else "None")

    # 3. Нормализуем
    content = normalize_tiktok(
        video,
        transcript=transcript,
    )

    print("\nCONTENT ITEM:")
    print(f"Caption: {content.text[:100]}")
    print(f"Transcript exists: {content.transcript is not None}")

    # 4. Сохраняем в PostgreSQL
    session = SessionLocal()

    try:
        saved = save_content(session, content)

        print("\nSAVED TO DATABASE:")
        print(f"ID: {saved.id}")
        print(f"External ID: {saved.external_id}")
        print(f"Transcript length: {len(saved.transcript or '')}")

    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(main())
