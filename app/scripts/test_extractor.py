import asyncio
import json
from pathlib import Path

from app.collectors.content_extractor import extract_content


SCRIPT_DIR = Path(__file__).resolve().parent

print("Скрипт находится здесь:")
print(SCRIPT_DIR)

print("\nФайлы в этой папке:")
for file in SCRIPT_DIR.iterdir():
    print(" -", file.name)


async def main():
    json_files = list(SCRIPT_DIR.glob("*.json"))

    if not json_files:
        print("\n❌ JSON-файл в этой папке не найден")
        return

    if len(json_files) > 1:
        print("\nНайдено несколько JSON-файлов:")
        for file in json_files:
            print(" -", file.name)

    file_path = json_files[0]

    print(f"\nИспользуем файл: {file_path}")

    with open(file_path, "r", encoding="utf-8") as file:
        videos = json.load(file)

    if not videos:
        print("❌ JSON пустой")
        return

    video = videos[0]

    print("\nVIDEO FOUND")
    print(f"URL: {video.get('webVideoUrl')}")
    print(f"Slideshow: {video.get('isSlideshow')}")
    print(
        f"Images: "
        f"{len(video.get('slideshowImageLinks', []))}"
    )

    content = await extract_content(video)

    print("\n" + "=" * 60)

    if content:
        print("EXTRACTED CONTENT:\n")
        print(content)
    else:
        print("CONTENT NOT AVAILABLE")


if __name__ == "__main__":
    asyncio.run(main())
