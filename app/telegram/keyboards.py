from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


def main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "🔥 Тренды",
                callback_data="trends",
            ),
        ],
        [
            InlineKeyboardButton(
                "⚙️ Настройки",
                callback_data="settings",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def settings_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "👤 Профили",
                callback_data="settings_profiles",
            ),
        ],
        [
            InlineKeyboardButton(
                "#️⃣ Хештеги",
                callback_data="settings_hashtags",
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 Количество видео",
                callback_data="settings_count",
            ),
        ],
        [
            InlineKeyboardButton(
                "📅 Свежесть видео",
                callback_data="settings_freshness",
            ),
        ],
        [
            InlineKeyboardButton(
                "✍️ Промпты",
                callback_data="settings_prompts",
            ),
        ],
        [
            InlineKeyboardButton(
                "🗂 Использованные TikTok",
                callback_data="used_tiktok_videos",
            ),
        ],
        [
            InlineKeyboardButton(
                "◀️ Главное меню",
                callback_data="menu",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def profile_settings_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "✏️ Изменить профили",
                callback_data="edit_profiles",
            ),
        ],
        [
            InlineKeyboardButton(
                "🗑 Очистить профили",
                callback_data="clear_profiles",
            ),
        ],
        [
            InlineKeyboardButton(
                "◀️ Настройки",
                callback_data="settings",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def hashtag_settings_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "✏️ Изменить хештеги",
                callback_data="edit_hashtags",
            ),
        ],
        [
            InlineKeyboardButton(
                "🗑 Очистить хештеги",
                callback_data="clear_hashtags",
            ),
        ],
        [
            InlineKeyboardButton(
                "◀️ Настройки",
                callback_data="settings",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def video_count_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "5",
                callback_data="count_5",
            ),
            InlineKeyboardButton(
                "10",
                callback_data="count_10",
            ),
        ],
        [
            InlineKeyboardButton(
                "20",
                callback_data="count_20",
            ),
            InlineKeyboardButton(
                "50",
                callback_data="count_50",
            ),
        ],
        [
            InlineKeyboardButton(
                "✏️ Свое количество",
                callback_data="count_custom",
            ),
        ],
        [
            InlineKeyboardButton(
                "◀️ Настройки",
                callback_data="settings",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def video_freshness_menu() -> InlineKeyboardMarkup:
    """Выбор минимальной даты публикации видео."""
    keyboard = [
        [
            InlineKeyboardButton(
                "За 1 день",
                callback_data="freshness_days_1",
            ),
            InlineKeyboardButton(
                "За 3 дня",
                callback_data="freshness_days_3",
            ),
        ],
        [
            InlineKeyboardButton(
                "За 7 дней",
                callback_data="freshness_days_7",
            ),
            InlineKeyboardButton(
                "За 30 дней",
                callback_data="freshness_days_30",
            ),
        ],
        [
            InlineKeyboardButton(
                "✏️ Указать дату",
                callback_data="freshness_custom",
            ),
        ],
        [
            InlineKeyboardButton(
                "♾ Без ограничения",
                callback_data="freshness_any",
            ),
        ],
        [
            InlineKeyboardButton(
                "◀️ Настройки",
                callback_data="settings",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def prompts_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💡 Промпт идеи",
                    callback_data="prompt_idea",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📝 Промпт поста",
                    callback_data="prompt_post",
                ),
            ],
            [
                InlineKeyboardButton(
                    "◀️ Настройки",
                    callback_data="settings",
                ),
            ],
        ]
    )


def used_tiktok_menu(
    allow_reparse: bool,
) -> InlineKeyboardMarkup:
    status = "✅ включён" if allow_reparse else "⛔ выключен"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"Повторный парсинг: {status}",
                    callback_data="toggle_used_tiktok_reparse",
                ),
            ],
            [
                InlineKeyboardButton(
                    "◀️ Настройки",
                    callback_data="settings",
                ),
            ],
        ]
    )


def prompt_editor_menu(
    prompt_type: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✏️ Изменить",
                    callback_data=f"edit_prompt_{prompt_type}",
                ),
                InlineKeyboardButton(
                    "↩️ Сбросить",
                    callback_data=f"reset_prompt_{prompt_type}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "◀️ К промптам",
                    callback_data="settings_prompts",
                ),
            ],
        ]
    )


def parsing_confirmation_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Запустить парсинг",
                callback_data="start_parsing",
            ),
        ],
        [
            InlineKeyboardButton(
                "⚙️ Изменить настройки",
                callback_data="settings",
            ),
        ],
        [
            InlineKeyboardButton(
                "◀️ Главное меню",
                callback_data="menu",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def source_errors_menu() -> InlineKeyboardMarkup:
    """Действия после частично успешного сбора данных."""
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Продолжить",
                callback_data="continue_parsing",
            ),
        ],
        [
            InlineKeyboardButton(
                "✏️ Исправить источники",
                callback_data="settings",
            ),
        ],
        [
            InlineKeyboardButton(
                "◀️ Главное меню",
                callback_data="menu",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def idea_result_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔄 Другая идея",
                    callback_data="regenerate_idea",
                ),
                InlineKeyboardButton(
                    "✏️ Изменить идею",
                    callback_data="edit_idea",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📝 Создать пост",
                    callback_data="post",
                ),
            ],
            [
                InlineKeyboardButton(
                    "◀️ К трендам",
                    callback_data="trends_list",
                ),
            ],
            [
                InlineKeyboardButton(
                    "◀️ Главное меню",
                    callback_data="menu",
                ),
            ],
        ]
    )


def post_result_menu(
    recheck: bool = False,
) -> InlineKeyboardMarkup:
    check_label = (
        "🔬 Проверить повторно по PubMed"
        if recheck
        else "🔬 Проверить по PubMed"
    )

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    check_label,
                    callback_data="check_post_pubmed",
                ),
            ],
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
    )


def pubmed_result_menu(
    needs_revision: bool,
) -> InlineKeyboardMarkup:
    keyboard = []

    if needs_revision:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "✍️ Исправить пост по PubMed",
                    callback_data="revise_post_pubmed",
                ),
            ]
        )

    keyboard.extend(
        [
            [
                InlineKeyboardButton(
                    "◀️ К посту",
                    callback_data="show_post",
                ),
            ],
            [
                InlineKeyboardButton(
                    "◀️ Главное меню",
                    callback_data="menu",
                ),
            ],
        ]
    )

    return InlineKeyboardMarkup(keyboard)


def trends_list_keyboard(
    videos: list,
) -> InlineKeyboardMarkup:
    keyboard = []

    for index, item in enumerate(
        videos,
        start=1,
    ):
        score = item["score"]

        button_text = (
            f"#{index} • Score: {score}"
        )

        keyboard.append(
            [
                InlineKeyboardButton(
                    button_text,
                    callback_data=(
                        f"trend_{index - 1}"
                    ),
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "◀️ Главное меню",
                callback_data="menu",
            )
        ]
    )

    return InlineKeyboardMarkup(keyboard)
