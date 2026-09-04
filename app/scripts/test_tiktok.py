import os
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
from app.normalizers.tiktok import normalize_tiktok


import asyncio
from apify_client import ApifyClientAsync
from app.collectors.apify_tiktok import collect_tiktok

async def main():
    # собираем видео с хештегом нутришен
    tiktok_videos = await collect_tiktok('nutrition')
    print(f"Successfully collected video: {len(tiktok_videos)}")

    for video in tiktok_videos[:5]:
        content = normalize_tiktok(video)
        print(content.model_dump_json(indent=4))


if __name__ == '__main__':
    # корректный запуск асинхронного скрипта
    asyncio.run(main())
