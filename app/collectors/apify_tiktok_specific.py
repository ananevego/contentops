import os

from apify_client import ApifyClientAsync
from dotenv import load_dotenv

load_dotenv()


async def collect_specific_tiktok(url: str):
    token = os.getenv("APIFY_TOKEN")

    if not token:
        raise RuntimeError("APIFY_TOKEN is not set")

    apify_client = ApifyClientAsync(token)

    actor_input = {
        "postURLs": [url],
        "resultsPerPage": 1,
        "downloadSubtitlesOptions": "DOWNLOAD_AND_TRANSCRIBE_VIDEOS_WITHOUT_SUBTITLES",
    }

    print(f"Collecting specific TikTok: {url}")

    run = await apify_client.actor(
        "clockworks/tiktok-scraper"
    ).call(
        run_input=actor_input,
        logger=None,
    )

    if not run:
        print("Error: failed to launch TikTok scraper")
        return None

    dataset_client = apify_client.dataset(
        run.default_dataset_id
    )

    result = await dataset_client.list_items()

    if not result.items:
        print("TikTok not found")
        return None

    return result.items[0]
