import os
import logging

from dotenv import load_dotenv
from openai import OpenAI

from app.models.content_db import ContentItemDB

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)
logger = logging.getLogger(__name__)

POST_MODELS = [
    "inclusionai/ling-3.0-flash-sante:free",
    "nex-agi/nex-n2.5-mini:free",
    "inclusionai/ling-3.0-flash-vl:free",
    "openrouter/free",
]

RUSSIAN_OUTPUT_INSTRUCTION = (
    "Отвечай только на русском языке. "
    "Не меняй язык ответа, даже если исходные материалы, идея "
    "или пользовательская инструкция написаны на другом языке."
)

MIN_POST_LENGTH = 1_200


def is_complete_post(
    post: str | None,
    finish_reason: str | None,
) -> bool:
    """Не пропускает оборванный ответ модели как готовый пост."""
    if not post or len(post.strip()) < MIN_POST_LENGTH:
        return False

    if finish_reason not in (None, "stop"):
        return False

    return post.rstrip().endswith((".", "!", "?", "…", ")", "»"))

DEFAULT_IDEA_PROMPT = """
Ты — контент-аналитик для экспертного Telegram-канала о питании,
диетологии и спорте.

Твоя задача — не пересказать TikTok, а определить,
ПОЧЕМУ он привлекает внимание и как на его основе создать
полезный оригинальный контент для Telegram.

Ответь строго по структуре:

1. ТЕМА
Одним предложением опиши главную тему TikTok.

2. HOOK
Какой элемент в начале, caption или основной формулировке
цепляет внимание аудитории?

3. ПОЧЕМУ ЭТО МОЖЕТ РАБОТАТЬ
Назови 2-3 причины, почему такой контент может
получать просмотры, комментарии или репосты.

4. ИДЕЯ ДЛЯ TELEGRAM
Предложи конкретную оригинальную тему для поста
в экспертном Telegram-канале.
Не копируй TikTok дословно.

5. ЗАГОЛОВОК
Предложи 3 варианта заголовка.

6. ФОРМАТ
Выбери наиболее подходящий формат:
- экспертный пост
- разбор мифа
- чек-лист
- инструкция
- вопрос аудитории
- опрос
- кейс
- другой
И объясни выбор одним предложением.

7. ПЛАН ПОСТА
Дай 4-6 конкретных пунктов, которые должны войти
в будущий пост.

8. CTA
Предложи один естественный призыв к действию
для читателя.

Важно:
- Используй Caption и извлечённое содержание видео как источники
  информации для анализа.
- Чётко отделяй факты из исходного TikTok от собственных идей
  для Telegram.
- Не приписывай исходному контенту продукты, цифры, исследования
  или выводы, которых нет в Caption или извлечённом содержании.
- Если информации недостаточно, прямо укажи это.
- Не выдумывай факты.
- Не утверждай медицинские эффекты без достаточных оснований.
- Не советуй опасные или экстремальные диеты.
- Главная цель — получить практичную идею,
  которую автор канала действительно сможет использовать.
""".strip()


DEFAULT_POST_PROMPT = """
Ты — редактор экспертного Telegram-канала о питании, диетологии и спорте.

На основе идеи ниже напиши готовый оригинальный пост на русском языке.

Требования:
- Дай сильный, но не кликбейтный заголовок.
- Пиши понятно, дружелюбно и по делу.
- Используй короткие абзацы; при необходимости — маркированный список.
- Не выдумывай факты, цифры, исследования или медицинские эффекты.
- Не копируй TikTok и не упоминай его.
- Заверши естественным CTA.
- Не добавляй пояснений редактора, только текст поста.
- Объём: 1 500–2 500 символов.
""".strip()


def generate_content_idea(
    item: ContentItemDB,
    instruction: str = DEFAULT_IDEA_PROMPT,
) -> str:
    extracted_content = item.transcript or "Не найдено"

    prompt = f"""{instruction}

Данные TikTok:

Автор: {item.author}

Caption TikTok:
{item.text}

Извлечённое содержание видео / OCR:
{extracted_content}

Метрики:

Просмотры: {item.views}
Лайки: {item.likes}
Комментарии: {item.comments}
Репосты: {item.shares}
Trend score: {item.trend_score}
Ссылка: {item.url}
"""

    response = client.chat.completions.create(
        model="qwen/qwen3-8b",
        messages=[
            {
                "role": "system",
                "content": RUSSIAN_OUTPUT_INSTRUCTION,
            },
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    return response.choices[0].message.content


def generate_telegram_post(
    idea: str,
    instruction: str = DEFAULT_POST_PROMPT,
) -> str:
    """Создаёт готовый Telegram-пост только по одобренной идее."""
    prompt = f"""{instruction}

ИДЕЯ:
{idea}
"""

    errors = []

    for model in POST_MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": RUSSIAN_OUTPUT_INSTRUCTION,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                max_tokens=1_400,
            )
            post = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason

            if is_complete_post(post, finish_reason):
                return post
            errors.append(
                f"{model}: неполный ответ ({finish_reason or 'без статуса'})"
            )
        except Exception as error:
            errors.append(f"{model}: {type(error).__name__}")

    logger.warning(
        "All free models failed post generation: %s",
        "; ".join(errors),
    )
    return (
        "📝 Черновик поста\n\n"
        f"{idea.strip()}\n\n"
        "💬 Что из этого откликается вам больше всего?"
    )
