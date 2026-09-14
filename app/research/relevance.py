import json
import os
import re

from openai import AsyncOpenAI
from dotenv import load_dotenv


# ==========================================================
# CONFIGURATION
# ==========================================================

# Загружаем переменные из .env.
#
# Нам нужен:
#
# OPENROUTER_API_KEY=...
#
# Мы не храним ключ внутри Python-кода.
load_dotenv()


# Модель, которую мы уже используем
# в нашем ContentOps.
#
# Здесь можно будет поменять модель позже,
# не переписывая всю логику агента.
MODEL_NAME = "qwen/qwen3-8b"


# OpenRouter предоставляет API,
# совместимый с OpenAI SDK.
OPENROUTER_BASE_URL = (
    "https://openrouter.ai/api/v1"
)


# ==========================================================
# CLIENT
# ==========================================================

def _get_client() -> AsyncOpenAI:
    """
    Создает OpenRouter/OpenAI client.

    Почему отдельная функция?

    Сейчас client нужен только одному модулю,
    но позже у нас будет несколько AI-задач:

        Content Agent
        Claim Extractor
        Research Agent
        Fact Checker
        Post Editor

    Отдельная функция позволяет
    не дублировать создание клиента.
    """

    api_key = os.getenv(
        "OPENROUTER_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set"
        )

    return AsyncOpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
    )


# ==========================================================
# JSON EXTRACTION
# ==========================================================

def _extract_json(
    text: str,
) -> list[dict]:
    """
    Пытается достать JSON из ответа модели.

    В идеальном случае Qwen вернет просто:

        [
            {
                "pmid": "...",
                "relevance": "RELEVANT",
                "reason": "..."
            }
        ]

    Но LLM иногда пишет:

        ```json
        [
            ...
        ]
        ```

    Поэтому сначала убираем markdown code fence.

    Это не полноценный универсальный JSON parser,
    а небольшой защитный слой для типичного ответа LLM.
    """

    text = text.strip()

    # Удаляем ```json ... ``` или ``` ... ```
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Qwen returned invalid JSON:\n"
            f"{text}"
        ) from exc

    if not isinstance(data, list):
        raise RuntimeError(
            "Qwen response must be a JSON list"
        )

    return data


# ==========================================================
# RELEVANCE AGENT
# ==========================================================

async def analyze_relevance(
    claim: str,
    articles: list[dict],
) -> list[dict]:
    """
    Определяет, насколько каждая PubMed-статья
    относится к конкретному научному claim.

    ВАЖНО:

    Эта функция НЕ проверяет, правда ли claim.

    Она отвечает только:

        эта статья действительно
        помогает проверить claim?

    Например:

        Claim:
        "Высокое потребление белка помогает
        сохранять мышечную массу при похудении."

        Article A:
        protein + obesity + lean mass
        -> RELEVANT

        Article B:
        high-fat diet + mice + platelets
        -> NOT_RELEVANT

    Это первый этап нашего Research Agent.
    """

    # ------------------------------------------------------
    # Проверяем входные данные
    # ------------------------------------------------------

    claim = claim.strip()

    if not claim:
        raise ValueError(
            "Claim cannot be empty"
        )

    if not articles:
        return []

    # ------------------------------------------------------
    # Создаем AI client
    # ------------------------------------------------------

    client = _get_client()

    # ------------------------------------------------------
    # Формируем evidence для модели
    # ------------------------------------------------------
    #
    # Мы НЕ передаем модели все поля статьи.
    #
    # Для проверки релевантности достаточно:
    #
    # PMID
    # Title
    # Abstract
    # Publication types
    # Date
    #
    # DOI и авторов на этом этапе можно не отправлять.
    #
    # Это уменьшает количество токенов.
    evidence = []

    for article in articles:

        evidence.append(
            {
                "pmid": article.get(
                    "pmid"
                ),
                "title": article.get(
                    "title",
                    "",
                ),
                "abstract": article.get(
                    "abstract",
                    "",
                ),
                "publication_types": (
                    article.get(
                        "publication_types",
                        [],
                    )
                ),
                "publication_date": (
                    article.get(
                        "publication_date",
                        "",
                    )
                ),
            }
        )

    # Превращаем Python list
    # в красивый JSON для prompt.
    evidence_json = json.dumps(
        evidence,
        ensure_ascii=False,
        indent=2,
    )

    # ------------------------------------------------------
    # SYSTEM PROMPT
    # ------------------------------------------------------
    #
    # Здесь мы максимально жестко ограничиваем задачу.
    #
    # Модель НЕ должна:
    #
    # - проверять истинность claim
    # - придумывать исследования
    # - использовать свои знания вместо evidence
    # - оценивать качество исследования
    #
    # Пока только relevance.
    system_prompt = """
You are a scientific literature relevance classifier.

Your task is ONLY to determine whether each supplied PubMed
article is relevant to the given scientific claim.

Do NOT determine whether the claim is true.

Do NOT infer scientific conclusions that are not explicitly
supported by the supplied article title and abstract.

Do NOT use outside knowledge.

For each article classify:

RELEVANT
- The article directly studies the population, intervention/
  exposure, outcome, or relationship needed to evaluate the claim.

NOT_RELEVANT
- The article is only superficially related by keywords or topic
  but does not meaningfully help evaluate the claim.

Return ONLY valid JSON.

Required format:

[
  {
    "pmid": "12345678",
    "relevance": "RELEVANT",
    "reason": "Short explanation"
  }
]

or:

[
  {
    "pmid": "12345678",
    "relevance": "NOT_RELEVANT",
    "reason": "Short explanation"
  }
]
""".strip()

    # ------------------------------------------------------
    # USER PROMPT
    # ------------------------------------------------------

    user_prompt = f"""
CLAIM:

{claim}


PUBMED ARTICLES:

{evidence_json}
""".strip()

    # ------------------------------------------------------
    # REQUEST TO QWEN
    # ------------------------------------------------------

    response = await client.chat.completions.create(
        model=MODEL_NAME,

        # System message задает правила агента.
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],

        # Нам нужен короткий классификатор,
        # поэтому высокая температура здесь не нужна.
        temperature=0,
    )

    # ------------------------------------------------------
    # Получаем текст ответа модели
    # ------------------------------------------------------

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "Qwen returned an empty response"
        )

    # ------------------------------------------------------
    # Разбираем JSON
    # ------------------------------------------------------

    results = _extract_json(
        content
    )

    # ------------------------------------------------------
    # Валидируем ответ
    # ------------------------------------------------------

    validated_results = []

    for result in results:

        if not isinstance(
            result,
            dict,
        ):
            continue

        pmid = result.get(
            "pmid"
        )

        relevance = result.get(
            "relevance"
        )

        reason = result.get(
            "reason"
        )

        # Проверяем обязательные поля.
        if not pmid:
            continue

        if relevance not in {
            "RELEVANT",
            "NOT_RELEVANT",
        }:
            continue

        if not isinstance(
            reason,
            str,
        ):
            reason = ""

        validated_results.append(
            {
                "pmid": str(pmid),
                "relevance": relevance,
                "reason": reason.strip(),
            }
        )

    # Если модель вернула что-то,
    # но ни один результат не прошел нашу валидацию,
    # лучше упасть с понятной ошибкой,
    # чем незаметно продолжить pipeline.
    if not validated_results:
        raise RuntimeError(
            "Qwen returned no valid relevance results"
        )

    return validated_results
