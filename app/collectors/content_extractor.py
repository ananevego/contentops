import tempfile
from pathlib import Path

from app.collectors.apify_ocr import (
    collect_local_frame_ocr,
    collect_slideshow_ocr,
    unique_ocr_texts,
)
from app.collectors.apify_transcript import collect_transcript
from app.collectors.video_frames import (
    download_video,
    extract_frames,
    get_video_duration,
)


MIN_TRANSCRIPT_LENGTH = 20


def has_meaningful_transcript(transcript: str | None) -> bool:
    return isinstance(transcript, str) and len(transcript.strip()) >= MIN_TRANSCRIPT_LENGTH


def get_download_url(video: dict) -> str | None:
    """Returns the direct video URL supplied by the existing TikTok Actor."""
    for field in ("videoUrlNoWaterMark", "videoUrl", "downloadAddr"):
        value = video.get(field)
        if isinstance(value, str) and value:
            return value
    return None


async def extract_video_ocr(video: dict) -> str | None:
    """Extracts up to five temporary frames and merges unique on-screen text."""
    download_url = get_download_url(video)
    if not download_url:
        print("Direct video URL not found for OCR fallback")
        return None

    with tempfile.TemporaryDirectory(prefix="tiktok-ocr-") as temporary_dir:
        temporary_path = Path(temporary_dir)
        video_path = temporary_path / "video.mp4"

        try:
            await download_video(download_url, video_path)
            duration = await get_video_duration(video_path)
            if not duration or duration <= 0:
                print("Video duration is unavailable for OCR fallback")
                return None

            first_timestamps = [
                duration / 6,
                duration / 2,
                duration * 5 / 6,
            ]
            first_frames = await extract_frames(
                video_path,
                first_timestamps,
                temporary_path,
            )
            first_results = await collect_local_frame_ocr(first_frames)
            unique_texts = unique_ocr_texts(first_results or [])

            if len(unique_texts) > 1:
                extra_frames = await extract_frames(
                    video_path,
                    [duration * 7 / 20, duration * 13 / 20],
                    temporary_path,
                )
                extra_results = await collect_local_frame_ocr(extra_frames)
                unique_texts = unique_ocr_texts(
                    unique_texts + (extra_results or [])
                )

            return "\n\n".join(unique_texts) or None
        except Exception as error:
            print(f"TikTok OCR fallback failed: {error}")
            return None


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
    transcript = await collect_transcript(url)
    if has_meaningful_transcript(transcript):
        return transcript.strip()

    print("Transcript is unavailable or insufficient → frame OCR")
    return await extract_video_ocr(video)
