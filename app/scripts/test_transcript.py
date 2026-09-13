import asyncio

from app.collectors.apify_transcript import collect_transcript


URL = "https://www.tiktok.com/@end.raitt/video/7682654407728565525?_r=1&_t=ZS-99ZPE0ISp8K"


async def main():
    transcript = await collect_transcript(URL)

    if transcript:
        print("\nTRANSCRIPT:")
        print(transcript)
    else:
        print("\nTRANSCRIPT NOT AVAILABLE")


if __name__ == "__main__":
    asyncio.run(main())
