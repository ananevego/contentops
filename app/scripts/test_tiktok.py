import asyncio
import requests

from app.collectors.apify_tiktok import collect_tiktok


async def main():
    tiktok_videos = await collect_tiktok("nutrition")

    print(f"Successfully collected videos: {len(tiktok_videos)}")
    print()

    for index, video in enumerate(tiktok_videos[:5], start=1):
        print("=" * 80)
        print(f"VIDEO #{index}")
        print("=" * 80)

        print("AUTHOR:")
        print(video.get("authorMeta", {}).get("name"))
        print()

        print("URL:")
        print(video.get("webVideoUrl"))
        print()

        print("IS SLIDESHOW:")
        print(video.get("isSlideshow"))
        print()

        video_meta = video.get("videoMeta", {})

        print("TRANSCRIPTION LINK:")
        print(video_meta.get("transcriptionLink"))
        print()

        subtitle_links = video_meta.get("subtitleLinks", [])

        print("SUBTITLE LINKS:")
        print(subtitle_links)
        print()

        if subtitle_links:
            subtitle_url = subtitle_links[0].get("downloadLink")

            print("SUBTITLE DOWNLOAD URL:")
            print(subtitle_url)
            print()

            response = requests.get(
                subtitle_url,
                timeout=30,
            )

            print("STATUS:")
            print(response.status_code)

            print("CONTENT-TYPE:")
            print(response.headers.get("content-type"))

            print("SIZE:")
            print(len(response.content))

            print()

    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
