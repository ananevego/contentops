import asyncio

from app.analytics.trends import calculate_trend_score
from app.collectors.apify_tiktok_specific import collect_specific_tiktok
from app.collectors.content_extractor import extract_content
from app.generators.content_ideas import generate_content_idea
from app.normalizers.tiktok import normalize_tiktok


TIKTOK_URL = "https://www.tiktok.com/@popupeni/video/7651895007338614034"


async def main():

    # Получаем свежие данные именно этого TikTok
    video = await collect_specific_tiktok(TIKTOK_URL)

    if not video:
        print("Video not found")
        return

    print("VIDEO:")
    print(f"URL: {video.get('webVideoUrl')}")
    print(f"Slideshow: {video.get('isSlideshow')}")
    print(
        f"Images: "
        f"{len(video.get('slideshowImageLinks', []))}"
    )
    print()

    # Извлекаем содержимое.
    # Для slideshow здесь автоматически запускается OCR.
    extracted_content = await extract_content(video)

    if not extracted_content:
        print("Extracted content not found")
        return

    print("OCR CONTENT:")
    print(extracted_content)
    print()

    # Нормализуем сырой ответ Apify
    # в наш единый ContentItem.
    content = normalize_tiktok(
        video,
        transcript=extracted_content,
    )

    # Рассчитываем trend score
    trend_score = calculate_trend_score(
        views=content.views,
        likes=content.likes,
        comments=content.comments,
        shares=content.shares,
        created_at=content.created_at,
    )

    print("NORMALIZED CONTENT:")
    print(f"Author: {content.author}")
    print(f"URL: {content.url}")
    print(f"Views: {content.views}")
    print()

    print("GENERATING CONTENT IDEA...")
    print()

    # Для генератора сейчас нужен ContentItemDB,
    # поэтому создаём объект только для теста.
    item = type(
        "ContentItemForGenerator",
        (),
        {
            "author": content.author,
            "text": content.text,
            "transcript": content.transcript,
            "views": content.views,
            "likes": content.likes,
            "comments": content.comments,
            "shares": content.shares,
            "url": content.url,
            "trend_score": trend_score,
        },
    )()

    result = generate_content_idea(item)

    print("=" * 80)
    print("QWEN RESULT")
    print("=" * 80)
    print()
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
