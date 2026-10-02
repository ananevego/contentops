import asyncio

from app.collectors import content_extractor
from app.collectors.apify_ocr import unique_ocr_texts


def test_unique_ocr_texts_collapses_near_identical_text():
    assert unique_ocr_texts(["  Call   to action ", "call to actlon"]) == [
        "Call   to action"
    ]


def test_extract_content_uses_transcript_when_it_is_meaningful(monkeypatch):
    async def transcript(_url):
        return "Это достаточно содержательный текст транскрипта."

    async def fallback(_video):
        raise AssertionError("OCR fallback must not run")

    monkeypatch.setattr(content_extractor, "collect_transcript", transcript)
    monkeypatch.setattr(content_extractor, "extract_video_ocr", fallback)

    result = asyncio.run(
        content_extractor.extract_content({"webVideoUrl": "https://tiktok.test/video"})
    )

    assert result == "Это достаточно содержательный текст транскрипта."


def test_extract_content_uses_ocr_when_transcript_is_insufficient(monkeypatch):
    async def transcript(_url):
        return "Коротко"

    async def fallback(video):
        assert video["videoUrl"] == "https://cdn.test/video.mp4"
        return "Текст на видео"

    monkeypatch.setattr(content_extractor, "collect_transcript", transcript)
    monkeypatch.setattr(content_extractor, "extract_video_ocr", fallback)

    result = asyncio.run(
        content_extractor.extract_content(
            {
                "webVideoUrl": "https://tiktok.test/video",
                "videoUrl": "https://cdn.test/video.mp4",
            }
        )
    )

    assert result == "Текст на видео"


def test_extract_video_ocr_uses_five_frames_only_when_first_texts_differ(monkeypatch):
    calls = []

    async def download(_url, _path):
        return None

    async def duration(_path):
        return 60

    async def frames(_video_path, timestamps, output_dir):
        calls.append(timestamps)
        return [output_dir / f"{len(calls)}-{index}.jpg" for index in range(len(timestamps))]

    async def ocr(frame_paths):
        return ["Первый экран", "Второй экран", "Третий экран"] if len(frame_paths) == 3 else ["Четвертый экран", "Второй экран"]

    monkeypatch.setattr(content_extractor, "download_video", download)
    monkeypatch.setattr(content_extractor, "get_video_duration", duration)
    monkeypatch.setattr(content_extractor, "extract_frames", frames)
    monkeypatch.setattr(content_extractor, "collect_local_frame_ocr", ocr)

    result = asyncio.run(
        content_extractor.extract_video_ocr({"videoUrl": "https://cdn.test/video.mp4"})
    )

    assert len(calls) == 2
    assert sum(len(timestamps) for timestamps in calls) == 5
    assert result == "Первый экран\n\nВторой экран\n\nТретий экран\n\nЧетвертый экран"


def test_extract_video_ocr_stops_after_three_matching_frames(monkeypatch):
    calls = []

    async def download(_url, _path):
        return None

    async def duration(_path):
        return 30

    async def frames(_video_path, timestamps, output_dir):
        calls.append(timestamps)
        return [output_dir / f"{index}.jpg" for index in range(len(timestamps))]

    async def ocr(_frame_paths):
        return ["Подпишитесь", "подпишитeсь", "ПОДПИШИТЕСЬ"]

    monkeypatch.setattr(content_extractor, "download_video", download)
    monkeypatch.setattr(content_extractor, "get_video_duration", duration)
    monkeypatch.setattr(content_extractor, "extract_frames", frames)
    monkeypatch.setattr(content_extractor, "collect_local_frame_ocr", ocr)

    result = asyncio.run(
        content_extractor.extract_video_ocr({"videoUrl": "https://cdn.test/video.mp4"})
    )

    assert len(calls) == 1
    assert len(calls[0]) == 3
    assert result == "Подпишитесь"
