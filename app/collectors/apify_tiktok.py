import asyncio
import os
from dotenv import load_dotenv
from apify_client import ApifyClientAsync

load_dotenv()

async def collect_tiktok(hashtag: str):
    token = os.getenv('APIFY_TOKEN')
    apify_client = ApifyClientAsync(token)
    
    actor_input = {
        "hashtags": [hashtag],
        "resultsPerPage": 5 #количество видео, которые хотим получить
    }

    print(f"Start collecting TikTok on the hashtag: #clockworks/tiktok-scraper {hashtag}...")

    run = await apify_client.actor('clockworks/tiktok-scraper').call(run_input=actor_input) #запускаем актор и передаем ему инпут

    if not run:
        print("Error: failed to launch the Actor")
        return []

    print("The collection is complete! We extract the dataset...")

    #получаем датасет и возвращаем результаты
    dataset_client = apify_client.dataset(run.default_dataset_id)
    list_items_result = await dataset_client.list_items()
    return list_items_result.items #возвращаем чистый список словарей


