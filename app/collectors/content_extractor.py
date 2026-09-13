from app.collectors.apify_ocr import collect_slideshow_ocr
from app.collectors.apify_transcript import collect_transcript


async def extract_content(video: dict) -> str | None:
    if video.get("isSlideshow"):
        image_links = video.get("slideshowImageLinks") or []

        image_urls = [
            image.get("downloadLink")
            for image in image_links
            if image.get("downloadLink")
        ]

        if not image_urls:
            print("Slideshow detected, but no images found")
            return None

        print(
            f"Slideshow detected: "
            f"{len(image_urls)} images → OCR"
        )

        ocr_results = await collect_slideshow_ocr(image_urls)

        if not ocr_results:
            return None

        return "\n\n".join(
            f"Фото {index}:\n{text}"
            for index, text in enumerate(ocr_results, start=1)
            if text
        )

    url = video.get("webVideoUrl")

    if not url:
        print("Video URL not found")
        return None

    print("Regular video detected → transcript")

    return await collect_transcript(url)
