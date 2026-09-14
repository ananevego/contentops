import os
import re

from apify_client import ApifyClientAsync
from dotenv import load_dotenv

load_dotenv()

TREND_VIDEO_FIELDS = [
    "id",
    "playCount",
    "diggCount",
    "commentCount",
    "shareCount",
    "createTimeISO",
]


def _matches_source(
    video: dict,
    source_type: str,
    clean_source: str,
) -> bool:
    """Проверяет, что Actor вернул видео именно запрошенного источника."""
    expected = clean_source.casefold()

    if source_type == "profile":
        author = video.get("authorMeta", {})
        author_names = (
            author.get("name"),
            author.get("uniqueId"),
        )
        return any(
            isinstance(name, str) and name.casefold() == expected
            for name in author_names
        )

    hashtag_names = set()

    for field in ("textExtra", "hashtags", "challenges"):
        values = video.get(field, [])
        if not isinstance(values, list):
            continue

        for value in values:
            if isinstance(value, str):
                hashtag_names.add(value.lstrip("#").casefold())
            elif isinstance(value, dict):
                name = (
                    value.get("hashtagName")
                    or value.get("name")
                    or value.get("title")
                )
                if isinstance(name, str):
                    hashtag_names.add(name.lstrip("#").casefold())

    if expected in hashtag_names:
        return True

    text = video.get("text", "")
    return isinstance(text, str) and bool(
        re.search(
            rf"(?<![\\w])#{re.escape(clean_source)}(?![\\w])",
            text,
            flags=re.IGNORECASE,
        )
    )


async def _collect_source(
    apify_client,
    source_type: str,
    source: str,
    results_count: int,
):
    """
    Получает видео из одного источника:
    одного профиля или одного хештега.

    Возвращает:
        videos, error
    """

    clean_source = source.lstrip("@#")

    actor_input = {
        "resultsPerPage": results_count,
    }

    if source_type == "profile":
        actor_input["profiles"] = [
            clean_source
        ]
        actor_input["profileScrapeSections"] = [
            "videos"
        ]
        actor_input["profileSorting"] = "latest"

    elif source_type == "hashtag":
        actor_input["hashtags"] = [
            clean_source
        ]

    try:
        print(
            f"Collecting {source_type}: "
            f"{source}"
        )

        run = await apify_client.actor(
            "clockworks/tiktok-scraper"
        ).call(
            run_input=actor_input,
            logger=None,
        )

        if not run:
            return [], (
                source_type,
                source,
                "не удалось запустить Apify Actor",
            )

        dataset_client = apify_client.dataset(
            run.default_dataset_id
        )

        validation_fields = (
            ["authorMeta"]
            if source_type == "profile"
            else []
        )
        result = await dataset_client.list_items(
            limit=results_count,
            fields=TREND_VIDEO_FIELDS + validation_fields,
        )

        videos_with_offsets = list(enumerate(result.items))

        # Actor иногда отдаёт непустой набор, даже если источника не
        # существует. Не считаем такой ответ успешным: иначе пользователь
        # не увидит ошибку для неверного @username или #хештега.
        if source_type == "profile":
            videos_with_offsets = [
                (offset, video)
                for offset, video in videos_with_offsets
                if _matches_source(
                    video=video,
                    source_type=source_type,
                    clean_source=clean_source,
                )
            ]

        if not videos_with_offsets:
            return [], (
                source_type,
                source,
                "источник не найден или "
                "не содержит доступных видео",
            )

        # В памяти бота оставляем только данные для Trend Score. Поля,
        # нужные для проверки источника, выше используются однократно.
        return [
            {
                field: video[field]
                for field in TREND_VIDEO_FIELDS
                if field in video
            }
            | {
                "_dataset_id": run.default_dataset_id,
                "_dataset_offset": offset,
            }
            for offset, video in videos_with_offsets
        ], None

    except Exception as e:
        print(
            f"Failed to collect "
            f"{source_type} {source}: {e}"
        )

        return [], (
            source_type,
            source,
            str(e),
        )


async def collect_tiktok(
    hashtags: list[str] | None = None,
    profiles: list[str] | None = None,
    results_count: int = 5,
):
    """
    Собирает видео по всем указанным источникам.

    results_count — это ОБЩЕЕ количество
    видео, которое будет возвращено.

    Например:

        3 профиля
        2 хештега
        results_count=5

    → собираем по всем источникам
    → возвращаем максимум 5 видео.

    Возвращает:

        {
            "videos": [...],
            "errors": [...]
        }
    """

    token = os.getenv("APIFY_TOKEN")

    if not token:
        raise RuntimeError(
            "APIFY_TOKEN is not set"
        )

    apify_client = ApifyClientAsync(token)

    hashtags = hashtags or []
    profiles = profiles or []

    all_videos = []
    errors = []

    # ==========================================
    # ПРОФИЛИ
    # ==========================================

    for profile in profiles:
        videos, error = await _collect_source(
            apify_client=apify_client,
            source_type="profile",
            source=profile,
            results_count=results_count,
        )

        all_videos.extend(videos)

        if error:
            errors.append(error)

    # ==========================================
    # ХЕШТЕГИ
    # ==========================================

    for hashtag in hashtags:
        videos, error = await _collect_source(
            apify_client=apify_client,
            source_type="hashtag",
            source=hashtag,
            results_count=results_count,
        )

        all_videos.extend(videos)

        if error:
            errors.append(error)

    # ==========================================
    # УБИРАЕМ ДУБЛИКАТЫ
    # ==========================================

    unique_videos = []
    seen_ids = set()

    for video in all_videos:
        video_id = video.get("id")

        if not video_id:
            continue

        if video_id in seen_ids:
            continue

        seen_ids.add(video_id)
        unique_videos.append(video)

    # ==========================================
    # ВАЖНО:
    # results_count = ОБЩИЙ лимит
    #
    # Пока не сортируем здесь по Trend Score,
    # потому что Score рассчитывается выше
    # в handlers.py.
    #
    # Поэтому возвращаем максимум нужного
    # количества после сбора.
    # ==========================================

    unique_videos = unique_videos[
        :results_count
    ]

    return {
        "videos": unique_videos,
        "errors": errors,
    }


async def collect_tiktok_details(
    trend_video: dict,
) -> dict | None:
    """Загружает полные данные только для одного выбранного тренда."""
    dataset_id = trend_video.get("_dataset_id")
    offset = trend_video.get("_dataset_offset")

    if not dataset_id or offset is None:
        return None

    token = os.getenv("APIFY_TOKEN")

    if not token:
        raise RuntimeError("APIFY_TOKEN is not set")

    apify_client = ApifyClientAsync(token)
    dataset_client = apify_client.dataset(dataset_id)
    result = await dataset_client.list_items(
        offset=offset,
        limit=1,
    )

    return result.items[0] if result.items else None


async def collect_tiktok_url(
    trend_video: dict,
) -> str | None:
    """Загружает только ссылку для выбранного тренда."""
    dataset_id = trend_video.get("_dataset_id")
    offset = trend_video.get("_dataset_offset")

    if not dataset_id or offset is None:
        return None

    token = os.getenv("APIFY_TOKEN")

    if not token:
        raise RuntimeError("APIFY_TOKEN is not set")

    apify_client = ApifyClientAsync(token)
    result = await apify_client.dataset(dataset_id).list_items(
        offset=offset,
        limit=1,
        fields=["webVideoUrl"],
    )

    if not result.items:
        return None

    return result.items[0].get("webVideoUrl")
