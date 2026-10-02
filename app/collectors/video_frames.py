"""Local temporary-frame extraction for TikTok OCR fallback."""

import asyncio
import shutil
import subprocess
from pathlib import Path
from urllib.request import urlopen


async def download_video(video_url: str, destination: Path) -> None:
    """Downloads a video to a caller-owned temporary file."""
    def _download() -> None:
        with urlopen(video_url, timeout=30) as response:
            destination.write_bytes(response.read())

    await asyncio.to_thread(_download)


async def get_video_duration(video_path: Path) -> float | None:
    """Reads video duration with the FFmpeg suite."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        print("FFprobe is not available for TikTok OCR fallback")
        return None

    def _probe() -> float | None:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            return float(result.stdout.strip()) if result.returncode == 0 else None
        except ValueError:
            return None

    return await asyncio.to_thread(_probe)


async def extract_frames(
    video_path: Path,
    timestamps: list[float],
    output_dir: Path,
) -> list[Path]:
    """Extracts one JPEG for each requested timestamp using local FFmpeg."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("FFmpeg is not available for TikTok OCR fallback")
        return []

    def _extract() -> list[Path]:
        frames = []
        for index, timestamp in enumerate(timestamps, start=1):
            frame_path = output_dir / f"frame-{index}.jpg"
            result = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-ss", str(timestamp),
                    "-i", str(video_path),
                    "-frames:v", "1",
                    "-q:v", "2",
                    str(frame_path),
                ],
                capture_output=True,
                check=False,
            )
            if result.returncode == 0 and frame_path.exists():
                frames.append(frame_path)
        return frames

    return await asyncio.to_thread(_extract)
