import asyncio
import logging

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
    prompts_menu,
    prompt_editor_menu,
    parsing_confirmation_menu,
    source_errors_menu,
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


def generate_idea_for_trend(
    video: dict,
    score: float,
    extracted_content: str | None,
    instruction: str,
) -> str:
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
        return generate_content_idea(item, instruction)


def get_user_settings(
    user_id: int,
) -> dict:
    if user_id not in user_settings:
        user_settings[user_id] = {
            "profiles": [],
            "hashtags": [],
            "results_count": 5,
        }

    return user_settings[user_id]


def get_prompt(
    settings: dict,
    prompt_type: str,
) -> str:
    default = (
        DEFAULT_IDEA_PROMPT
        if prompt_type == "idea"
        else DEFAULT_POST_PROMPT
    )
    return settings.get(f"{prompt_type}_prompt", default)


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

    return (
        "📊 НАСТРОЙКИ ПАРСИНГА\n\n"
        f"👤 Профили:\n"
        f"{profiles_text}\n\n"
        f"#️⃣ Хештеги:\n"
        f"{hashtags_text}\n\n"
        f"📹 Количество видео:\n"
        f"{results_count}\n\n"
        "Проверь настройки и подтверди "
        "запуск парсинга."
    )


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
        "🤖 ContentOps\n\n"
        "Я помогу находить тренды в TikTok "
        "и превращать их в идеи для Telegram.",
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
            "⏳ Apify собирает данные..."
        )

        collection = await collect_tiktok(
            hashtags=hashtags,
            profiles=profiles,
            results_count=results_count,
        )
        videos = collection["videos"][:results_count]
        errors = collection["errors"]

        if not videos:
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

    if query.data.startswith("analyze_"):
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
            trend = trends[index]
            video = await collect_tiktok_details(trend["video"])

            if not video:
                raise ValueError("не удалось загрузить данные видео")

            stage = "получения транскрипции или OCR"
            extracted_content = await extract_content(video)

            stage = "сохранения и генерации идеи"
            idea = await asyncio.to_thread(
                generate_idea_for_trend,
                video,
                trend["score"],
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
                f"Ошибка на этапе: {stage}.\n"
                f"Тип ошибки: {type(error).__name__}.\n"
                "Подробности записаны в журнал бота.",
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

        await query.edit_message_text(
            f"💡 ИДЕЯ ДЛЯ TELEGRAM\n\n{idea}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📝 Создать пост",
                            callback_data="post",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "◀️ К трендам",
                            callback_data="trends_list",
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

    # ======================================
    # ИДЕЯ
    # ======================================

    if query.data == "idea":
        idea = context.user_data.get("latest_idea")

        if idea:
            await query.edit_message_text(
                f"💡 ИДЕЯ ДЛЯ TELEGRAM\n\n{idea}",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "📝 Создать пост",
                                callback_data="post",
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

        await query.edit_message_text(
            "💡 ИДЕЯ ДЛЯ TELEGRAM\n\n"
            "Сначала выбери тренд в разделе «🔥 Тренды», "
            "затем нажми «💡 Получить идею».\n\n"
            "Полные данные и транскрипция будут запрошены "
            "только для выбранного ролика.",
            reply_markup=main_menu(),
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
                f"Тип ошибки: {type(error).__name__}.\n"
                "Все бесплатные модели временно недоступны или "
                "исчерпан лимит запросов. Попробуй позже.",
                reply_markup=main_menu(),
            )
            return

        await query.edit_message_text(
            f"📝 ГОТОВЫЙ ПОСТ\n\n{post[:3800]}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "💡 К идее",
                            callback_data="idea",
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
            "Выбери, какой промпт посмотреть или изменить.\n\n"
            "Данные TikTok и текст идеи бот добавляет автоматически.",
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
            "Отправь новый текст инструкции одним сообщением.\n\n"
            "Данные TikTok и идея будут добавлены ботом автоматически.",
        )
        return

    if query.data.startswith("reset_prompt_"):
        prompt_type = query.data.removeprefix("reset_prompt_")
        settings = get_user_settings(user_id)
        settings.pop(f"{prompt_type}_prompt", None)
        title = "идеи" if prompt_type == "idea" else "поста"

        await query.edit_message_text(
            f"✅ Стандартный промпт {title} восстановлен.",
            reply_markup=prompt_editor_menu(prompt_type),
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
            f"{profiles_text}\n\n"
            "Можно указать несколько профилей "
            "через пробел.\n\n"
            "Например:\n"
            "@profile1 @profile2 @profile3",
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
            f"{hashtags_text}\n\n"
            "Можно указать несколько хештегов "
            "через пробел.\n\n"
            "Например:\n"
            "#nutrition #diet #fitness",
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

        await query.edit_message_text(
            "✅ Хештеги очищены.",
            reply_markup=settings_menu(),
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
            f"{current_count}\n\n"
            "Сколько видео получать?",
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
        context.user_data.pop("waiting_for", None)
        title = "идеи" if waiting_for == "idea_prompt" else "поста"

        await update.message.reply_text(
            f"✅ Промпт {title} сохранён.",
            reply_markup=prompts_menu(),
        )
        return

    # ======================================
    # СВОЕ КОЛИЧЕСТВО ВИДЕО
    # ======================================

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
