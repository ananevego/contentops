import os
import re
from pathlib import Path
from difflib import SequenceMatcher
from uuid import uuid4

from apify_client import ApifyClientAsync
from dotenv import load_dotenv


load_dotenv()


def normalize_ocr_text(text: str) -> str:
    """Normalizes OCR output for comparison without changing returned text."""
    return re.sub(r"\s+", " ", text).strip().casefold()


def are_ocr_texts_similar(first: str, second: str) -> bool:
    """Treats minor OCR variations as the same caption."""
    normalized_first = normalize_ocr_text(first)
    normalized_second = normalize_ocr_text(second)

    if not normalized_first or not normalized_second:
        return normalized_first == normalized_second

    return SequenceMatcher(
        None,
        normalized_first,
        normalized_second,
    ).ratio() >= 0.9


def unique_ocr_texts(texts: list[str]) -> list[str]:
    """Keeps the first representative of each distinct OCR caption."""
    unique_texts = []

    for text in texts:
        if not isinstance(text, str) or not text.strip():
            continue

        cleaned_text = text.strip()
        if not any(
            are_ocr_texts_similar(cleaned_text, existing)
            for existing in unique_texts
        ):
            unique_texts.append(cleaned_text)

    return unique_texts


async def collect_ocr(image_urls: list[str]) -> list[str] | None:
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


async def collect_slideshow_ocr(image_urls: list[str]) -> list[str] | None:
    """Backward-compatible OCR entry point for TikTok slideshows."""
    return await collect_ocr(image_urls)


async def collect_local_frame_ocr(frame_paths: list[Path]) -> list[str] | None:
    """Temporarily exposes local frames to the existing OCR Actor, then deletes them."""
    token = os.getenv("APIFY_TOKEN")

    if not token or not frame_paths:
        return None

    apify_client = ApifyClientAsync(token)
    store_name = f"tiktok-ocr-frames-{uuid4()}"
    store_data = await apify_client.key_value_stores().get_or_create(
        name=store_name,
    )
    store = apify_client.key_value_store(store_data.id)

    try:
        image_urls = []
        for index, frame_path in enumerate(frame_paths, start=1):
            record_key = f"frame-{index}.jpg"
            await store.set_record(
                record_key,
                frame_path.read_bytes(),
                content_type="image/jpeg",
            )
            image_urls.append(await store.get_record_public_url(record_key))

        return await collect_ocr(image_urls)
    finally:
        await store.delete()
