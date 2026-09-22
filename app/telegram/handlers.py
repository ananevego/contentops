import asyncio
import logging
from datetime import datetime, time, timedelta, timezone

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    ContextTypes,
)

from app.analytics.trends import (
    calculate_trend_score,
)
from app.telegram.keyboards import (
    main_menu,
    settings_menu,
    profile_settings_menu,
    hashtag_settings_menu,
    video_count_menu,
    video_freshness_menu,
    prompts_menu,
    prompt_editor_menu,
    used_tiktok_menu,
    parsing_confirmation_menu,
    source_errors_menu,
    idea_result_menu,
    post_result_menu,
    pubmed_result_menu,
    trends_list_keyboard,
)
from app.collectors.apify_tiktok import (
    collect_tiktok,
    collect_tiktok_details,
    collect_tiktok_url,
)
from app.collectors.content_extractor import (
    extract_content,
)
from app.generators.content_ideas import (
    DEFAULT_IDEA_PROMPT,
    DEFAULT_POST_PROMPT,
)


user_settings = {}
user_trends = {}
logger = logging.getLogger(__name__)


def explain_error(error: Exception, action: str) -> str:
    """Переводит ошибки внешних сервисов в действия, понятные пользователю."""
    error_type = type(error).__name__
    message = str(error).lower()

    if error_type == "OperationalError":
        return (
            "PostgreSQL сейчас недоступен. Попробуй ещё раз через минуту; "
            "если ошибка повторится, нужно проверить базу данных."
        )
    if "429" in message or "rate limit" in message:
        return (
            "Сервис временно ограничил число запросов. "
            "Подожди несколько минут и повтори попытку."
        )
    if "apify" in message:
        return "Apify временно недоступен. Повтори попытку позже."
    if "openrouter" in message or "model" in message:
        return (
            "Модель сейчас не ответила. Бот попробует резервные варианты; "
            "если сообщение повторяется, повтори попытку позже."
        )
    if "timeout" in message or "timed out" in message:
        return "Сервис не ответил вовремя. Повтори попытку через минуту."

    return f"Не удалось завершить {action}. Попробуй ещё раз."


def generate_idea_for_trend(
    video: dict,
    score: float,
    extracted_content: str | None,
    instruction: str,
) -> tuple[str, int]:
    """Сохраняет один выбранный тренд и создаёт идею вне event loop."""
    from app.database import SessionLocal
    from app.generators.content_ideas import (
        generate_content_idea,
    )
    from app.normalizers.tiktok import normalize_tiktok
    from app.repositories.content import save_content

    content = normalize_tiktok(
        video,
        transcript=extracted_content,
    )

    with SessionLocal() as session:
        item = save_content(session, content)
        item.trend_score = score
        session.commit()
        session.refresh(item)
        return generate_content_idea(item, instruction), item.id


def get_user_settings(
    user_id: int,
) -> dict:
    if user_id not in user_settings:
        try:
            from app.database import SessionLocal
            from app.repositories.telegram_state import (
                get_user_settings as get_persisted_settings,
            )

            with SessionLocal() as session:
                user_settings[user_id] = get_persisted_settings(session, user_id)
        except Exception:
            logger.exception("Failed to load Telegram settings for %s", user_id)
            user_settings[user_id] = {
                "profiles": [],
                "hashtags": [],
                "results_count": 5,
                "min_video_date": None,
                "idea_prompt": None,
                "post_prompt": None,
                "allow_reparse_used_videos": False,
            }

    return user_settings[user_id]


def save_settings(user_id: int, settings: dict) -> bool:
    """Сохраняет кешированные настройки; False означает ошибку PostgreSQL."""
    try:
        from app.database import SessionLocal
        from app.repositories.telegram_state import save_user_settings

        with SessionLocal() as session:
            save_user_settings(session, user_id, settings)
        return True
    except Exception:
        logger.exception("Failed to save Telegram settings for %s", user_id)
        # Не оставляем в памяти изменения, которых нет в PostgreSQL. Иначе
        # бот покажет их до перезапуска, а затем они неожиданно исчезнут.
        user_settings.pop(user_id, None)
        return False


async def report_settings_save_error(update: Update) -> None:
    """Сообщает об ошибке сохранения вместо ложного подтверждения."""
    await update.effective_message.reply_text(
        "❌ Не удалось сохранить настройку: PostgreSQL недоступен. "
        "Попробуй ещё раз через минуту.",
    )


def get_used_video_ids(user_id: int) -> set[str]:
    try:
        from app.database import SessionLocal
        from app.repositories.telegram_state import get_used_video_ids as load_ids

        with SessionLocal() as session:
            return load_ids(session, user_id)
    except Exception:
        logger.exception("Failed to load used TikTok videos for %s", user_id)
        return set()


def remember_video_for_post(
    user_id: int,
    video: dict,
    content_id: int | None,
) -> None:
    try:
        from app.database import SessionLocal
        from app.repositories.telegram_state import remember_used_video

        with SessionLocal() as session:
            remember_used_video(session, user_id, video, content_id)
    except Exception:
        logger.exception("Failed to save used TikTok video for %s", user_id)


def format_used_videos(user_id: int) -> str:
    """Показывает последние ролики, по которым уже создан пост."""
    try:
        from app.database import SessionLocal
        from app.repositories.telegram_state import list_used_videos

        with SessionLocal() as session:
            videos = list_used_videos(session, user_id)
    except Exception:
        logger.exception("Failed to list used TikTok videos for %s", user_id)
        return "❌ Не удалось загрузить список использованных TikTok."

    if not videos:
        return "🗂 ИСПОЛЬЗОВАННЫЕ TIKTOK\n\nПока нет роликов, по которым создан пост."

    lines = ["🗂 ИСПОЛЬЗОВАННЫЕ TIKTOK", ""]
    for index, video in enumerate(videos, start=1):
        author = f"@{video.author}" if video.author else "автор неизвестен"
        link = video.url or "ссылка недоступна"
        used_at = video.used_at.strftime("%d.%m.%Y")
        lines.append(f"{index}. {author} · {used_at}\n{link}")

    return "\n\n".join(lines)


def get_prompt(
    settings: dict,
    prompt_type: str,
) -> str:
    default = (
        DEFAULT_IDEA_PROMPT
        if prompt_type == "idea"
        else DEFAULT_POST_PROMPT
    )
    return settings.get(f"{prompt_type}_prompt") or default


def format_pubmed_report(
    result: dict,
) -> str:
    """Создаёт компактный отчёт PubMed для Telegram."""
    verdict_names = {
        "SUPPORTED": "✅ Подтверждён",
        "PARTIALLY_SUPPORTED": "⚠️ Частично подтверждён",
        "CONTRADICTED": "❌ Противоречит данным",
        "INSUFFICIENT_EVIDENCE": "❓ Недостаточно данных",
    }
    lines = ["🔬 ПРОВЕРКА ПО PUBMED", ""]

    claims = result.get("claims", [])

    if not claims:
        return "\n".join(
            lines + [
                "В посте не найдено научно проверяемых утверждений.",
            ]
        )

    for index, claim in enumerate(claims, start=1):
        verdict = claim.get("verdict", "INSUFFICIENT_EVIDENCE")
        lines.extend(
            [
                f"{index}. {verdict_names.get(verdict, verdict)}",
                f"Тезис: {claim.get('claim', '')}",
                f"Вывод: {claim.get('reason', '')}",
            ]
        )

        if claim.get("source"):
            lines.append(f"Источник: {claim['source']}")

        lines.append("")

    return "\n".join(lines)


def format_parsing_settings(
    settings: dict,
) -> str:
    profiles = settings.get(
        "profiles",
        [],
    )

    hashtags = settings.get(
        "hashtags",
        [],
    )

    results_count = settings.get(
        "results_count",
        5,
    )
    min_video_date = settings.get("min_video_date")

    if profiles:
        profiles_text = ", ".join(
            f"@{profile.lstrip('@')}"
            for profile in profiles
        )
    else:
        profiles_text = "не заданы"

    if hashtags:
        hashtags_text = ", ".join(
            f"#{hashtag.lstrip('#')}"
            for hashtag in hashtags
        )
    else:
        hashtags_text = "не заданы"

    if min_video_date:
        freshness_text = datetime.strptime(
            min_video_date,
            "%Y-%m-%d",
        ).strftime("%d.%m.%Y")
    else:
        freshness_text = "без ограничений"

    return (
        "📊 НАСТРОЙКИ ПАРСИНГА\n\n"
        f"👤 Профили:\n"
        f"{profiles_text}\n\n"
        f"#️⃣ Хештеги:\n"
        f"{hashtags_text}\n\n"
        f"📹 Количество видео:\n"
        f"{results_count}\n\n"
        f"📅 Искать видео с даты:\n"
        f"{freshness_text}\n\n"
        "Проверь настройки и подтверди "
        "запуск парсинга."
    )


def filter_videos_by_date(
    videos: list[dict],
    min_video_date: str | None,
) -> list[dict]:
    """Оставляет видео, опубликованные не раньше выбранной даты."""
    if not min_video_date:
        return videos

    boundary = datetime.combine(
        datetime.strptime(min_video_date, "%Y-%m-%d").date(),
        time.min,
        tzinfo=timezone.utc,
    )
    fresh_videos = []

    for video in videos:
        created_at = video.get("createTimeISO")
        if not created_at:
            continue

        try:
            published_at = datetime.fromisoformat(
                created_at.replace("Z", "+00:00"),
            )
        except (TypeError, ValueError):
            continue

        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)

        if published_at >= boundary:
            fresh_videos.append(video)

    return fresh_videos


def format_source_errors(errors: list) -> str:
    """Форматирует ошибки источников для сообщения пользователю."""
    lines = []

    for source_type, source, reason in errors:
        prefix = "@" if source_type == "profile" else "#"
        source_name = source.lstrip("@#")
        source_label = (
            "Профиль" if source_type == "profile" else "Хештег"
        )

        if reason == (
            "источник не найден или не содержит доступных видео"
        ):
            reason = "не найден или не содержит доступных видео"

        lines.append(
            f"• {source_label} {prefix}{source_name}: {reason}"
        )

    return "\n".join(lines)


async def show_scored_trends(
    query,
    user_id: int,
    videos: list,
    results_count: int,
):
    """Рассчитывает Score и показывает не больше выбранного лимита."""
    await query.edit_message_text(
        f"📊 Получено видео: {len(videos)}\n\n"
        "🧮 Рассчитываю Trend Score..."
    )

    scored_videos = []

    for video in videos[:results_count]:
        try:
            score = calculate_trend_score(
                views=video.get("playCount", 0),
                likes=video.get("diggCount", 0),
                comments=video.get("commentCount", 0),
                shares=video.get("shareCount", 0),
                created_at=video["createTimeISO"],
            )

            scored_videos.append(
                {
                    "video": video,
                    "score": score,
                }
            )

        except Exception as error:
            print(f"Failed to calculate score: {error}")

    scored_videos.sort(
        key=lambda item: item["score"],
        reverse=True,
    )
    scored_videos = scored_videos[:results_count]
    user_trends[user_id] = scored_videos

    if not scored_videos:
        await query.edit_message_text(
            "❌ Не удалось рассчитать Trend Score.",
            reply_markup=main_menu(),
        )
        return

    await query.edit_message_text(
        "🔥 TOP TikTok-трендов\n\n"
        "Рейтинг отсортирован по Trend Score.\n"
        "Чем выше Score — тем выше позиция в TOP.\n\n"
        f"Показано видео: {len(scored_videos)}",
        reply_markup=trends_list_keyboard(scored_videos),
    )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🤖 ContentOps\n"
        "Помогаю с созданием постов в Telegram на основе трендов TikTok",
        reply_markup=main_menu(),
    )


async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    # ======================================
    # ГЛАВНОЕ МЕНЮ
    # ======================================

    if query.data == "menu":
        await query.edit_message_text(
            "🤖 ContentOps\n\n"
            "Выбери действие:",
            reply_markup=main_menu(),
        )
        return

    # ======================================
    # ТРЕНДЫ
    # ======================================

    if query.data == "trends":
        settings = get_user_settings(
            user_id
        )

        await query.edit_message_text(
            format_parsing_settings(
                settings
            ),
            reply_markup=(
                parsing_confirmation_menu()
            ),
        )
        return

    # ======================================
    # ЗАПУСК ПАРСИНГА
    # ======================================

    if query.data == "start_parsing":
        settings = get_user_settings(
            user_id
        )

        hashtags = settings.get(
            "hashtags",
            [],
        )

        profiles = settings.get(
            "profiles",
            [],
        )

        results_count = settings.get(
            "results_count",
            5,
        )
        min_video_date = settings.get("min_video_date")

        if not hashtags and not profiles:
            await query.edit_message_text(
                "⚠️ Не указаны источники "
                "для парсинга.\n\n"
                "Добавь хотя бы один "
                "хештег или профиль.",
                reply_markup=settings_menu(),
            )
            return

        await query.edit_message_text(
            "🔥 Начинаю парсинг...\n\n"
            f"👤 Профили: {len(profiles)}\n"
            f"#️⃣ Хештеги: {len(hashtags)}\n"
            f"📹 Видео: {results_count}\n\n"
            f"📅 С даты: {min_video_date or 'без ограничений'}\n\n"
            "⏳ Apify собирает данные..."
        )

        try:
            collection = await collect_tiktok(
                hashtags=hashtags,
                profiles=profiles,
                results_count=results_count,
            )
        except Exception as error:
            logger.exception("Failed to collect TikTok trends")
            await query.edit_message_text(
                "❌ Не удалось получить видео.\n\n"
                f"Причина: {explain_error(error, 'поиск трендов')}",
                reply_markup=settings_menu(),
            )
            return
        videos = filter_videos_by_date(
            collection["videos"],
            min_video_date,
        )
        if not settings.get("allow_reparse_used_videos", False):
            used_video_ids = get_used_video_ids(user_id)
            videos = [
                video
                for video in videos
                if str(video.get("id", "")) not in used_video_ids
            ]
        videos = videos[:results_count]
        errors = collection["errors"]

        if not videos:
            if min_video_date:
                formatted_date = datetime.strptime(
                    min_video_date,
                    "%Y-%m-%d",
                ).strftime("%d.%m.%Y")
                await query.edit_message_text(
                    "❌ Не найдено видео, опубликованных "
                    f"с {formatted_date}.\n\n"
                    "Выбери более раннюю дату или отключи ограничение.",
                    reply_markup=settings_menu(),
                )
                return

            if (
                not settings.get("allow_reparse_used_videos", False)
                and not errors
            ):
                await query.edit_message_text(
                    "❌ Новых видео не найдено.\n\n"
                    "Ролики, по которым уже создавался пост, исключены из "
                    "выдачи. В разделе «🗂 Использованные TikTok» можно "
                    "разрешить их повторный парсинг.",
                    reply_markup=settings_menu(),
                )
                return

            errors_text = format_source_errors(errors)
            await query.edit_message_text(
                "❌ Не удалось получить видео.\n\n"
                f"{errors_text or 'Проверь профили и хештеги.'}",
                reply_markup=settings_menu(),
            )
            return

        if errors:
            context.user_data["pending_videos"] = videos
            context.user_data["pending_results_count"] = results_count

            await query.edit_message_text(
                "⚠️ Не все источники удалось обработать:\n\n"
                f"{format_source_errors(errors)}\n\n"
                f"Найдено видео: {len(videos)}. Продолжить с ними?",
                reply_markup=source_errors_menu(),
            )
            return

        await show_scored_trends(
            query=query,
            user_id=user_id,
            videos=videos,
            results_count=results_count,
        )
        return

    if query.data == "continue_parsing":
        videos = context.user_data.pop("pending_videos", [])
        results_count = context.user_data.pop("pending_results_count", 5)

        if not videos:
            await query.edit_message_text(
                "❌ Данные для продолжения не найдены. Запусти парсинг ещё раз.",
                reply_markup=main_menu(),
            )
            return

        await show_scored_trends(
            query=query,
            user_id=user_id,
            videos=videos,
            results_count=results_count,
        )
        return

    # ======================================
    # КОНКРЕТНЫЙ ТРЕНД
    # ======================================

    if query.data.startswith("trend_"):
        index = int(
            query.data.split("_")[1]
        )

        videos = user_trends.get(
            user_id,
            [],
        )

        if index >= len(videos):
            await query.edit_message_text(
                "❌ Видео не найдено.",
                reply_markup=main_menu(),
            )
            return

        item = videos[index]
        video = item["video"]
        score = item["score"]

        url = video.get("_web_video_url")

        if url is None:
            try:
                url = await collect_tiktok_url(video)
                video["_web_video_url"] = url
            except Exception as error:
                print(f"Failed to load TikTok URL: {error}")

        views = video.get(
            "playCount",
            0,
        )

        likes = video.get(
            "diggCount",
            0,
        )

        comments = video.get(
            "commentCount",
            0,
        )

        shares = video.get(
            "shareCount",
            0,
        )

        keyboard = []

        if url:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "🎬 Открыть видео",
                        url=url,
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "💡 Получить идею",
                    callback_data=(
                        f"analyze_{index}"
                    ),
                )
            ]
        )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "◀️ К трендам",
                    callback_data="trends_list",
                )
            ]
        )

        await query.edit_message_text(
            f"🔥 ТРЕНД #{index + 1}\n\n"
            f"📊 Trend Score: {score}\n\n"
            f"👀 Просмотры: {views}\n"
            f"❤️ Лайки: {likes}\n"
            f"💬 Комментарии: {comments}\n"
            f"🔄 Репосты: {shares}",
            reply_markup=(
                InlineKeyboardMarkup(
                    keyboard
                )
            ),
        )
        return

    # ======================================
    # СПИСОК ТРЕНДОВ
    # ======================================

    if query.data == "trends_list":
        videos = user_trends.get(
            user_id,
            [],
        )

        if not videos:
            await query.edit_message_text(
                "❌ Список трендов пуст.",
                reply_markup=main_menu(),
            )
            return

        await query.edit_message_text(
            "🔥 TOP TikTok-трендов\n\n"
            "Рейтинг по Trend Score.",
            reply_markup=(
                trends_list_keyboard(
                    videos
                )
            ),
        )
        return

    # ======================================
    # АНАЛИЗ
    # ======================================

    if (
        query.data.startswith("analyze_")
        or query.data == "regenerate_idea"
    ):
        if query.data == "regenerate_idea":
            index = context.user_data.get("latest_trend_index")

            if index is None:
                await query.edit_message_text(
                    "❌ Сначала выбери тренд и создай идею.",
                    reply_markup=main_menu(),
                )
                return
        else:
            index = int(
                query.data.split("_")[1]
            )

        trends = user_trends.get(user_id, [])

        if index >= len(trends):
            await query.edit_message_text(
                "❌ Тренд не найден. Запусти поиск ещё раз.",
                reply_markup=main_menu(),
            )
            return

        await query.edit_message_text(
            "💡 Готовлю идею...\n\n"
            "Получаю содержание только выбранного видео."
        )

        stage = "загрузки данных TikTok"

        try:
            cached_context = context.user_data.get(
                "latest_idea_context"
            )

            if query.data == "regenerate_idea" and cached_context:
                video = cached_context["video"]
                extracted_content = cached_context[
                    "extracted_content"
                ]
                score = cached_context["score"]
            else:
                trend = trends[index]
                video = await collect_tiktok_details(trend["video"])

                if not video:
                    raise ValueError("не удалось загрузить данные видео")

                stage = "получения транскрипции или OCR"
                extracted_content = await extract_content(video)
                score = trend["score"]

            stage = "сохранения и генерации идеи"
            idea, content_id = await asyncio.to_thread(
                generate_idea_for_trend,
                video,
                score,
                extracted_content,
                get_prompt(
                    get_user_settings(user_id),
                    "idea",
                ),
            )

        except Exception as error:
            logger.exception(
                "Failed to generate idea at stage %s",
                stage,
            )
            await query.edit_message_text(
                "❌ Не удалось создать идею.\n\n"
                f"Не выполнен этап: {stage}.\n"
                f"Причина: {explain_error(error, 'создание идеи')}",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "◀️ К тренду",
                                callback_data=f"trend_{index}",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "◀️ Главное меню",
                                callback_data="menu",
                            )
                        ],
                    ]
                ),
            )
            return

        context.user_data["latest_idea"] = idea
        context.user_data["latest_trend_index"] = index
        context.user_data["latest_idea_context"] = {
            "video": video,
            "score": score,
            "extracted_content": extracted_content,
            "content_id": content_id,
        }

        await query.edit_message_text(
            f"💡 ИДЕЯ ДЛЯ TELEGRAM\n\n{idea}",
            reply_markup=idea_result_menu(),
        )
        return

    # ======================================
    # ИДЕЯ
    # ======================================

    if query.data == "idea":
        idea = context.user_data.get("latest_idea")

        if idea:
            await query.edit_message_text(
                f"💡 ИДЕЯ ДЛЯ TELEGRAM\n\n{idea}",
                reply_markup=idea_result_menu(),
            )
            return

        await query.edit_message_text(
            "💡 ИДЕЯ ДЛЯ TELEGRAM\n\n"
            "Сначала выбери тренд в разделе «🔥 Тренды», "
            "затем нажми «💡 Получить идею».\n\n"
            "Полные данные и транскрипция будут запрошены "
            "только для выбранного ролика.",
            reply_markup=main_menu(),
        )
        return

    if query.data == "edit_idea":
        if not context.user_data.get("latest_idea"):
            await query.edit_message_text(
                "❌ Сначала создай идею для выбранного тренда.",
                reply_markup=main_menu(),
            )
            return

        context.user_data["waiting_for"] = "edit_idea"
        await query.edit_message_text(
            "✏️ РЕДАКТИРОВАНИЕ ИДЕИ\n\n"
            "Отправь полный обновлённый текст идеи одним сообщением."
        )
        return

    # ======================================
    # ПОСТ
    # ======================================

    if query.data == "post":
        idea = context.user_data.get("latest_idea")

        if not idea:
            await query.edit_message_text(
                "📝 СОЗДАНИЕ ПОСТА\n\n"
                "Сначала создай идею для выбранного тренда.",
                reply_markup=main_menu(),
            )
            return

        await query.edit_message_text(
            "📝 Создаю готовый пост по идее..."
        )

        try:
            from app.generators.content_ideas import (
                generate_telegram_post,
            )

            post = await asyncio.to_thread(
                generate_telegram_post,
                idea,
                get_prompt(
                    get_user_settings(user_id),
                    "post",
                ),
            )
        except Exception as error:
            logger.exception("Failed to generate Telegram post")
            await query.edit_message_text(
                "❌ Не удалось создать пост.\n\n"
                f"Причина: {explain_error(error, 'создание поста')}",
                reply_markup=main_menu(),
            )
            return

        await query.edit_message_text(
            f"📝 ГОТОВЫЙ ПОСТ\n\n{post[:3800]}",
            reply_markup=post_result_menu(),
        )
        context.user_data["latest_post"] = post
        context.user_data.pop("latest_fact_check", None)
        context.user_data["post_revised_by_pubmed"] = False
        latest_context = context.user_data.get("latest_idea_context", {})
        remember_video_for_post(
            user_id,
            latest_context.get("video", {}),
            latest_context.get("content_id"),
        )
        return

    if query.data == "show_post":
        post = context.user_data.get("latest_post")

        if not post:
            await query.edit_message_text(
                "❌ Готовый пост не найден.",
                reply_markup=main_menu(),
            )
            return

        await query.edit_message_text(
            f"📝 ГОТОВЫЙ ПОСТ\n\n{post[:3800]}",
            reply_markup=post_result_menu(
                context.user_data.get("post_revised_by_pubmed", False),
            ),
        )
        return

    if query.data == "check_post_pubmed":
        post = context.user_data.get("latest_post")

        if not post:
            await query.edit_message_text(
                "❌ Сначала создай готовый пост.",
                reply_markup=main_menu(),
            )
            return

        await query.edit_message_text(
            "🔬 Проверяю пост по исследованиям PubMed...\n\n"
            "Выделяю тезисы, ищу статьи и сравниваю формулировки."
        )

        try:
            from app.research.fact_checker import check_post

            fact_check = await check_post(post)
        except Exception as error:
            logger.exception("Failed to check post with PubMed")
            await query.edit_message_text(
                "❌ Не удалось проверить пост по PubMed.\n\n"
                f"Причина: {explain_error(error, 'проверку по PubMed')}",
                reply_markup=post_result_menu(),
            )
            return

        context.user_data["latest_fact_check"] = fact_check
        needs_revision = (
            fact_check.get("overall_verdict") == "NEEDS_REVISION"
        )
        report = format_pubmed_report(fact_check)

        await query.edit_message_text(
            report[:3800],
            reply_markup=pubmed_result_menu(needs_revision),
            disable_web_page_preview=True,
        )
        return

    if query.data == "revise_post_pubmed":
        post = context.user_data.get("latest_post")
        fact_check = context.user_data.get("latest_fact_check")

        if not post or not fact_check:
            await query.edit_message_text(
                "❌ Сначала запусти проверку готового поста по PubMed.",
                reply_markup=main_menu(),
            )
            return

        await query.edit_message_text(
            "✍️ Исправляю пост только по выводам PubMed..."
        )

        try:
            from app.research.post_reviser import (
                revise_post_from_pubmed,
            )

            revised_post = await asyncio.to_thread(
                revise_post_from_pubmed,
                post,
                fact_check,
            )
        except Exception as error:
            logger.exception("Failed to revise post with PubMed")
            await query.edit_message_text(
                "❌ Не удалось исправить пост.\n\n"
                f"Причина: {explain_error(error, 'исправление поста')}",
                reply_markup=pubmed_result_menu(True),
            )
            return

        context.user_data["latest_post"] = revised_post
        context.user_data.pop("latest_fact_check", None)
        context.user_data["post_revised_by_pubmed"] = True

        await query.edit_message_text(
            f"📝 ПОСТ ПОСЛЕ ПРОВЕРКИ PUBMED\n\n{revised_post[:3800]}",
            reply_markup=post_result_menu(recheck=True),
        )
        return

    # ======================================
    # НАСТРОЙКИ
    # ======================================

    if query.data == "settings":
        settings = get_user_settings(
            user_id
        )

        await query.edit_message_text(
            format_parsing_settings(
                settings
            ),
            reply_markup=settings_menu(),
        )
        return

    # ======================================
    # ПРОМПТЫ
    # ======================================

    if query.data == "settings_prompts":
        await query.edit_message_text(
            "✍️ ПРОМПТЫ\n\n"
            "Выбери, какой промпт посмотреть или изменить.\n",
            reply_markup=prompts_menu(),
        )
        return

    if query.data in ("prompt_idea", "prompt_post"):
        prompt_type = query.data.removeprefix("prompt_")
        title = "💡 ПРОМПТ ИДЕИ" if prompt_type == "idea" else "📝 ПРОМПТ ПОСТА"
        prompt = get_prompt(
            get_user_settings(user_id),
            prompt_type,
        )

        await query.edit_message_text(
            f"{title}\n\n{prompt}",
            reply_markup=prompt_editor_menu(prompt_type),
        )
        return

    if query.data.startswith("edit_prompt_"):
        prompt_type = query.data.removeprefix("edit_prompt_")
        context.user_data["waiting_for"] = f"{prompt_type}_prompt"
        title = "идеи" if prompt_type == "idea" else "поста"

        await query.edit_message_text(
            f"✏️ ВВОД ПРОМПТА {title.upper()}\n\n"
            "Отправь новый текст инструкции одним сообщением.\n",
        )
        return

    if query.data.startswith("reset_prompt_"):
        prompt_type = query.data.removeprefix("reset_prompt_")
        settings = get_user_settings(user_id)
        settings.pop(f"{prompt_type}_prompt", None)
        if not save_settings(user_id, settings):
            await report_settings_save_error(update)
            return
        title = "идеи" if prompt_type == "idea" else "поста"

        await query.edit_message_text(
            f"✅ Стандартный промпт {title} восстановлен.",
            reply_markup=prompt_editor_menu(prompt_type),
        )
        return

    # ======================================
    # ИСПОЛЬЗОВАННЫЕ TIKTOK
    # ======================================

    if query.data == "used_tiktok_videos":
        settings = get_user_settings(user_id)
        await query.edit_message_text(
            format_used_videos(user_id),
            reply_markup=used_tiktok_menu(
                settings.get("allow_reparse_used_videos", False),
            ),
            disable_web_page_preview=True,
        )
        return

    if query.data == "toggle_used_tiktok_reparse":
        settings = get_user_settings(user_id)
        enabled = not settings.get("allow_reparse_used_videos", False)
        settings["allow_reparse_used_videos"] = enabled
        saved = save_settings(user_id, settings)
        status = "включён" if enabled else "выключен"
        if not saved:
            await query.edit_message_text(
                "❌ Не удалось сохранить настройку: PostgreSQL недоступен. "
                "Попробуй ещё раз через минуту.",
                reply_markup=used_tiktok_menu(
                    not enabled,
                ),
            )
            return

        await query.edit_message_text(
            f"✅ Повторный парсинг использованных TikTok {status}.",
            reply_markup=used_tiktok_menu(enabled),
        )
        return

    # ======================================
    # ПРОФИЛИ
    # ======================================

    if query.data == "settings_profiles":
        settings = get_user_settings(
            user_id
        )

        profiles = settings.get(
            "profiles",
            [],
        )

        if profiles:
            profiles_text = "\n".join(
                f"• @{profile.lstrip('@')}"
                for profile in profiles
            )
        else:
            profiles_text = (
                "Профили не заданы."
            )

        await query.edit_message_text(
            "👤 ПРОФИЛИ\n\n"
            f"{profiles_text}\n"
            "Можно указать несколько профилей "
            "через пробел.\n",
            reply_markup=profile_settings_menu(),
        )
        return

    # ======================================
    # НАЧАТЬ РЕДАКТИРОВАНИЕ ПРОФИЛЕЙ
    # ======================================

    if query.data == "edit_profiles":
        context.user_data[
            "waiting_for"
        ] = "profiles"

        await query.edit_message_text(
            "👤 ВВОД ПРОФИЛЕЙ\n\n"
            "Отправь usernames профилей "
            "через пробел.\n\n"
            "Например:\n"
            "@hubermanlab @thefitnesschef\n\n"
            "Можно также написать без @:\n"
            "hubermanlab thefitnesschef"
        )
        return

    # ======================================
    # ОЧИСТИТЬ ПРОФИЛИ
    # ======================================

    if query.data == "clear_profiles":
        settings = get_user_settings(
            user_id
        )

        settings["profiles"] = []
        if not save_settings(user_id, settings):
            await report_settings_save_error(update)
            return

        await query.edit_message_text(
            "✅ Профили очищены.",
            reply_markup=settings_menu(),
        )
        return

    # ======================================
    # ХЕШТЕГИ
    # ======================================

    if query.data == "settings_hashtags":
        settings = get_user_settings(
            user_id
        )

        hashtags = settings.get(
            "hashtags",
            [],
        )

        if hashtags:
            hashtags_text = "\n".join(
                f"• #{hashtag.lstrip('#')}"
                for hashtag in hashtags
            )
        else:
            hashtags_text = (
                "Хештеги не заданы."
            )

        await query.edit_message_text(
            "#️⃣ ХЕШТЕГИ\n\n"
            f"{hashtags_text}\n"
            "Можно указать несколько хештегов "
            "через пробел.\n\n",
            reply_markup=hashtag_settings_menu(),
        )
        return

    # ======================================
    # НАЧАТЬ РЕДАКТИРОВАНИЕ ХЕШТЕГОВ
    # ======================================

    if query.data == "edit_hashtags":
        context.user_data[
            "waiting_for"
        ] = "hashtags"

        await query.edit_message_text(
            "#️⃣ ВВОД ХЕШТЕГОВ\n\n"
            "Отправь хештеги через пробел.\n\n"
            "Например:\n"
            "#nutrition #diet #fitness\n\n"
            "Можно также без #:\n"
            "nutrition diet fitness"
        )
        return

    # ======================================
    # ОЧИСТИТЬ ХЕШТЕГИ
    # ======================================

    if query.data == "clear_hashtags":
        settings = get_user_settings(
            user_id
        )

        settings["hashtags"] = []
        if not save_settings(user_id, settings):
            await report_settings_save_error(update)
            return

        await query.edit_message_text(
            "✅ Хештеги очищены.",
            reply_markup=settings_menu(),
        )
        return

    # ======================================
    # СВЕЖЕСТЬ ВИДЕО
    # ======================================

    if query.data == "settings_freshness":
        min_video_date = get_user_settings(user_id).get("min_video_date")
        current = (
            datetime.strptime(min_video_date, "%Y-%m-%d").strftime("%d.%m.%Y")
            if min_video_date
            else "без ограничений"
        )

        await query.edit_message_text(
            "📅 СВЕЖЕСТЬ ВИДЕО\n\n"
            f"Искать видео с даты: {current}\n"
            "Выбери период или укажи точную дату.",
            reply_markup=video_freshness_menu(),
        )
        return

    if query.data == "freshness_custom":
        context.user_data["waiting_for"] = "min_video_date"
        await query.edit_message_text(
            "📅 СВОЯ ДАТА\n\n"
            "Отправь дату, с которой искать видео.\n"
            "Формат: ДД.ММ.ГГГГ или ГГГГ-ММ-ДД\n",
        )
        return

    if query.data == "freshness_any":
        settings = get_user_settings(user_id)
        settings["min_video_date"] = None
        if not save_settings(user_id, settings):
            await report_settings_save_error(update)
            return
        await query.edit_message_text(
            "✅ Ограничение по дате отключено.",
            reply_markup=parsing_confirmation_menu(),
        )
        return

    if query.data.startswith("freshness_days_"):
        days = int(query.data.removeprefix("freshness_days_"))
        min_video_date = (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).date().isoformat()
        settings = get_user_settings(user_id)
        settings["min_video_date"] = min_video_date
        if not save_settings(user_id, settings):
            await report_settings_save_error(update)
            return
        formatted_date = datetime.strptime(
            min_video_date,
            "%Y-%m-%d",
        ).strftime("%d.%m.%Y")

        await query.edit_message_text(
            f"✅ Будут показаны видео с {formatted_date}.",
            reply_markup=parsing_confirmation_menu(),
        )
        return

    # ======================================
    # КОЛИЧЕСТВО ВИДЕО
    # ======================================

    if query.data == "settings_count":
        settings = get_user_settings(
            user_id
        )

        current_count = settings.get(
            "results_count",
            5,
        )

        await query.edit_message_text(
            "📊 КОЛИЧЕСТВО ВИДЕО\n\n"
            f"Текущее значение: "
            f"{current_count}\n\n",
            reply_markup=video_count_menu(),
        )
        return

    # ======================================
    # СОХРАНЕНИЕ КОЛИЧЕСТВА
    # ======================================

    if query.data == "count_custom":
        context.user_data["waiting_for"] = "results_count"

        await query.edit_message_text(
            "📊 СВОЕ КОЛИЧЕСТВО ВИДЕО\n\n"
            "Отправь целое число от 1 до 100.\n\n"
            "Чем больше значение, тем больше запросов к Apify "
            "и выше стоимость парсинга."
        )
        return

    if query.data.startswith("count_"):
        settings = get_user_settings(
            user_id
        )

        count = int(
            query.data.split("_")[1]
        )

        settings[
            "results_count"
        ] = count
        if not save_settings(user_id, settings):
            await report_settings_save_error(update)
            return

        await query.edit_message_text(
            "✅ Настройка сохранена.\n\n"
            f"📊 Количество видео: {count}",
            reply_markup=settings_menu(),
        )
        return


# ==========================================
# ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ
# ==========================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = update.effective_user.id

    waiting_for = context.user_data.get(
        "waiting_for"
    )

    if not waiting_for:
        await update.message.reply_text(
            "Используй кнопки меню 👇",
            reply_markup=main_menu(),
        )
        return

    text = update.message.text.strip()

    if not text:
        await update.message.reply_text(
            "❌ Пустое значение. "
            "Попробуй ещё раз."
        )
        return

    settings = get_user_settings(
        user_id
    )

    # ======================================
    # ПОЛЬЗОВАТЕЛЬСКИЕ ПРОМПТЫ
    # ======================================

    if waiting_for in ("idea_prompt", "post_prompt"):
        if len(text) > 3500:
            await update.message.reply_text(
                "❌ Промпт слишком длинный. Максимум — 3 500 символов."
            )
            return

        settings[waiting_for] = text
        if not save_settings(user_id, settings):
            await report_settings_save_error(update)
            return
        context.user_data.pop("waiting_for", None)
        title = "идеи" if waiting_for == "idea_prompt" else "поста"

        await update.message.reply_text(
            f"✅ Промпт {title} сохранён.",
            reply_markup=prompts_menu(),
        )
        return

    # ======================================
    # РЕДАКТИРОВАНИЕ ИДЕИ
    # ======================================

    if waiting_for == "edit_idea":
        if len(text) > 3500:
            await update.message.reply_text(
                "❌ Идея слишком длинная. Максимум — 3 500 символов."
            )
            return

        context.user_data["latest_idea"] = text
        context.user_data.pop("waiting_for", None)

        await update.message.reply_text(
            f"✅ Идея обновлена.\n\n💡 ИДЕЯ ДЛЯ TELEGRAM\n\n{text}",
            reply_markup=idea_result_menu(),
        )
        return

    # ======================================
    # СВОЯ ДАТА ВИДЕО
    # ======================================

    if waiting_for == "min_video_date":
        parsed_date = None
        for date_format in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                parsed_date = datetime.strptime(text, date_format).date()
                break
            except ValueError:
                pass

        if not parsed_date:
            await update.message.reply_text(
                "❌ Введи дату в формате ДД.ММ.ГГГГ или ГГГГ-ММ-ДД."
            )
            return

        if parsed_date > datetime.now(timezone.utc).date():
            await update.message.reply_text(
                "❌ Дата не может быть в будущем."
            )
            return

        settings["min_video_date"] = parsed_date.isoformat()
        if not save_settings(user_id, settings):
            await report_settings_save_error(update)
            return
        context.user_data.pop("waiting_for", None)

        await update.message.reply_text(
            f"✅ Будут показаны видео с {parsed_date.strftime('%d.%m.%Y')}.",
            reply_markup=parsing_confirmation_menu(),
        )
        return

    # ======================================
    # СВОЕ КОЛИЧЕСТВО ВИДЕО

    if waiting_for == "results_count":
        try:
            count = int(text)
        except ValueError:
            await update.message.reply_text(
                "❌ Введи целое число от 1 до 100."
            )
            return

        if not 1 <= count <= 100:
            await update.message.reply_text(
                "❌ Можно указать число от 1 до 100."
            )
            return

        settings["results_count"] = count
        if not save_settings(user_id, settings):
            await report_settings_save_error(update)
            return
        context.user_data.pop("waiting_for", None)

        await update.message.reply_text(
            "✅ Настройка сохранена.\n\n"
            f"📊 Количество видео: {count}",
            reply_markup=parsing_confirmation_menu(),
        )
        return

    # ======================================
    # ПРОФИЛИ
    # ======================================

    if waiting_for == "profiles":
        profiles = text.split()

        cleaned_profiles = []

        for profile in profiles:
            profile = (
                profile
                .strip()
                .lstrip("@")
                .strip()
            )

            if profile:
                cleaned_profiles.append(
                    profile
                )

        # Убираем дубликаты,
        # сохраняя порядок.
        cleaned_profiles = list(
            dict.fromkeys(
                cleaned_profiles
            )
        )

        settings["profiles"] = (
            cleaned_profiles
        )
        if not save_settings(user_id, settings):
            await report_settings_save_error(update)
            return

        context.user_data.pop(
            "waiting_for",
            None,
        )

        if cleaned_profiles:
            profiles_text = "\n".join(
                f"• @{profile}"
                for profile in cleaned_profiles
            )
        else:
            profiles_text = (
                "Профили не заданы."
            )

        await update.message.reply_text(
            "✅ Профили сохранены.\n\n"
            f"{profiles_text}",
            reply_markup=parsing_confirmation_menu(),
        )

        return

    # ======================================
    # ХЕШТЕГИ
    # ======================================

    if waiting_for == "hashtags":
        hashtags = text.split()

        cleaned_hashtags = []

        for hashtag in hashtags:
            hashtag = (
                hashtag
                .strip()
                .lstrip("#")
                .strip()
            )

            if hashtag:
                cleaned_hashtags.append(
                    hashtag
                )

        cleaned_hashtags = list(
            dict.fromkeys(
                cleaned_hashtags
            )
        )

        settings["hashtags"] = (
            cleaned_hashtags
        )
        if not save_settings(user_id, settings):
            await report_settings_save_error(update)
            return

        context.user_data.pop(
            "waiting_for",
            None,
        )

        if cleaned_hashtags:
            hashtags_text = "\n".join(
                f"• #{hashtag}"
                for hashtag in cleaned_hashtags
            )
        else:
            hashtags_text = (
                "Хештеги не заданы."
            )

        await update.message.reply_text(
            "✅ Хештеги сохранены.\n\n"
            f"{hashtags_text}",
            reply_markup=parsing_confirmation_menu(),
        )

        return
