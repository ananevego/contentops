import os


from apify_client import ApifyClientAsync
from dotenv import load_dotenv

load_dotenv()

async def collect_transcript(url: str) -> str | None:
    token = os.getenv("APIFY_TOKEN")

    if not token:
        raise RuntimeError("APIFY_TOKEN is not set")

    apify_client = ApifyClientAsync(token)

    actor_input = {
        "videoUrls" : [url],
    }

    try:
        run = await apify_client.actor(
            "aticode/tiktok-transcript-scraper"
        ).call(
            run_input=actor_input,
            logger=None,
        )

        if not run:
            print("Error: failed to launch transcription Actor")
            return None

        dataset_client = apify_client.dataset(
            run.default_dataset_id
        )

        result = await dataset_client.list_items()

        if not result.items:
            print("Transcription not found")
            return None

        item = result.items[0]

        transcript = item.get("transcript")

        if not isinstance(transcript, str) or not transcript.strip():
            print("Transcription is unavailable")
            return None

        return transcript

        
    except Exception as e:
        print(f"Transcription Actor failed: {e}")
        return None
