import os

from apify_client import ApifyClientAsync
from dotenv import load_dotenv


load_dotenv()


async def collect_slideshow_ocr(image_urls: list[str]) -> str | None:
    token = os.getenv("APIFY_TOKEN")

    if not token:
        raise RuntimeError("APIFY_TOKEN is not set")

    if not image_urls:
        print("No slideshow images found")
        return None

    apify_client = ApifyClientAsync(token)

    actor_input = {
        "imageUrls": image_urls,
        "urlsFromFile": "",
        "languages": ["rus", "eng"],
        "pageSegmentation": "auto",
        "preferTextLayer": True,
        "dpi": 200,
        "includePageText": True,
        "includeWords": False,
        "maxPagesPerPdf": 20,
        "maxItems": 100,
        "maxFileMb": 30,
    }

    try:
        run = await apify_client.actor(
            "scrapesage/ocr-text-extractor"
        ).call(
            run_input=actor_input,
            logger=None,
        )

        if not run:
            print("Error: failed to launch OCR Actor")
            return None

        dataset_client = apify_client.dataset(
            run.default_dataset_id
        )

        result = await dataset_client.list_items()

        if not result.items:
            print("OCR results not found")
            return None

        texts = []

        for item in result.items:
            text = item.get("text")

            if isinstance(text, str) and text.strip():
                texts.append(text.strip())

        if not texts:
            print("OCR text is unavailable")
            return None

        return texts

    except Exception as e:
        print(f"OCR Actor failed: {e}")
        return None
