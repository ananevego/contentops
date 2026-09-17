import json
import os
import re

from dotenv import load_dotenv
from openai import AsyncOpenAI

from app.research.pubmed import (
    search_and_fetch_pubmed,
)


# ==========================================================
# НАСТРОЙКИ
# ==========================================================

# Загружаем переменные из .env.
#
# Нам нужен:
#
# OPENROUTER_API_KEY=...
#
# API-ключ не хранится непосредственно в коде.
load_dotenv()


# Используем ту же модель Qwen,
# которую уже подключили для генерации контента.
MODEL_NAME = "qwen/qwen3-8b"


# OpenRouter предоставляет API,
# совместимый с OpenAI SDK.
OPENROUTER_BASE_URL = (
    "https://openrouter.ai/api/v1"
)


# ==========================================================
# OPENROUTER CLIENT
# ==========================================================

def _get_client() -> AsyncOpenAI:
    """
    Создает клиент OpenRouter.

    Ключ берем из .env.
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
# JSON PARSER
# ==========================================================

def _extract_json(text: str):
    """
    Преобразует ответ Qwen в Python-объект.

    Иногда модель возвращает JSON внутри:

        ```json
        {...}
        ```

    Поэтому сначала удаляем markdown-обертку.
    """

    text = text.strip()

    # Убираем начало:
    #
    # ```json
    #
    # или:
    #
    # ```
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Убираем закрывающую ```
    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    try:
        return json.loads(text)

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Qwen returned invalid JSON:\n"
            f"{text}"
        ) from exc


# ==========================================================
# ШАГ 1
# ИЗВЛЕЧЕНИЕ НАУЧНЫХ ТЕЗИСОВ
# ==========================================================

async def _extract_claims(
    client: AsyncOpenAI,
    post: str,
) -> list[dict]:
    """
    Читает готовый Telegram-пост и выделяет
    научно проверяемые утверждения.

    Для каждого утверждения возвращает:

        claim
        search_query

    claim:
        исходный тезис из поста.

    search_query:
        поисковый запрос для PubMed.
    """

    system_prompt = """
Ты — помощник по проверке научных утверждений
для Telegram-канала о питании и фитнесе.

Прочитай переданный Telegram-пост и выдели ТОЛЬКО те
утверждения, которые можно проверить по научной литературе
в PubMed.

Игнорируй:
- мнения;
- шутки;
- риторические фразы;
- личный опыт;
- призывы к действию;
- субъективные оценки.

Для каждого утверждения верни:

1. claim — само научное утверждение.
2. search_query — короткий поисковый запрос для PubMed.

Правила:
- Не придумывай утверждения, которых нет в посте.
- Не меняй смысл исходного утверждения.
- Сохраняй формулировку как можно ближе к исходному тексту.
- Максимум 5 утверждений.

Обычный текст пиши на русском языке.

search_query может содержать английские научные термины,
если это улучшает поиск в PubMed.

Верни ТОЛЬКО корректный JSON:

[
  {
    "claim": "научное утверждение",
    "search_query": "PubMed search query"
  }
]
""".strip()

    user_prompt = f"""
ТЕЛЕГРАМ-ПОСТ:

{post}
""".strip()

    response = await client.chat.completions.create(
        model=MODEL_NAME,
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
        temperature=0,
    )

    content = (
        response.choices[0]
        .message
        .content
    )

    if not content:
        raise RuntimeError(
            "Qwen returned an empty claim extraction response"
        )

    data = _extract_json(
        content
    )

    if not isinstance(
        data,
        list,
    ):
        raise RuntimeError(
            "Claim extraction response must be a list"
        )

    claims = []

    for item in data:

        if not isinstance(
            item,
            dict,
        ):
            continue

        claim = item.get(
            "claim"
        )

        search_query = item.get(
            "search_query"
        )

        if not isinstance(
            claim,
            str,
        ):
            continue

        if not isinstance(
            search_query,
            str,
        ):
            continue

        claim = claim.strip()
        search_query = search_query.strip()

        if not claim or not search_query:
            continue

        claims.append(
            {
                "claim": claim,
                "search_query": search_query,
            }
        )

    return claims[:5]


# ==========================================================
# ШАГ 2
# ПОИСК СТАТЕЙ В PUBMED
# ==========================================================

async def _collect_evidence(
    claims: list[dict],
) -> list[dict]:
    """
    Для каждого научного тезиса делает поиск в PubMed.

    PubMed возвращает несколько кандидатов.
    Позже Qwen выберет из них наиболее подходящую статью.
    """

    evidence = []

    for claim_data in claims:

        claim = claim_data[
            "claim"
        ]

        search_query = claim_data[
            "search_query"
        ]

        print(
            f"\nПоиск в PubMed:\n"
            f"{search_query}"
        )

        articles = await search_and_fetch_pubmed(
            query=search_query,
            max_results=5,
        )

        evidence.append(
            {
                "claim": claim,
                "search_query": search_query,
                "articles": articles,
            }
        )

    return evidence


# ==========================================================
# ШАГ 3
# ПРОВЕРКА ТЕЗИСА ПО ЛУЧШЕЙ СТАТЬЕ
# ==========================================================

async def _check_evidence(
    client: AsyncOpenAI,
    evidence: list[dict],
) -> list[dict]:
    """
    Для каждого тезиса:

    1. смотрит найденные статьи;
    2. выбирает одну наиболее подходящую;
    3. сравнивает тезис с этой статьей;
    4. пишет короткий вывод на русском;
    5. переводит название выбранной статьи на русский.

    Внутри Qwen может получить несколько статей,
    но пользователю мы показываем только одну.
    """

    results = []

    for item in evidence:

        claim = item[
            "claim"
        ]

        articles = item[
            "articles"
        ]

        # --------------------------------------------------
        # Если PubMed ничего не нашел
        # --------------------------------------------------

        if not articles:

            results.append(
                {
                    "claim": claim,
                    "verdict": (
                        "INSUFFICIENT_EVIDENCE"
                    ),
                    "reason": (
                        "В PubMed не найдено "
                        "подходящих исследований "
                        "по этому запросу."
                    ),
                    "best_pmid": None,
                    "article_title_ru": None,
                }
            )

            continue

        # --------------------------------------------------
        # Подготавливаем статьи для Qwen
        # --------------------------------------------------

        articles_for_model = []

        for article in articles:

            articles_for_model.append(
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

        articles_json = json.dumps(
            articles_for_model,
            ensure_ascii=False,
            indent=2,
        )

        # --------------------------------------------------
        # SYSTEM PROMPT
        # --------------------------------------------------

        system_prompt = """
Ты — научный фактчекер для Telegram-канала
о питании и фитнесе.

Ты получаешь ОДИН научный тезис и несколько
кандидатных статей из PubMed.

Твои задачи:

1. Выбрать ОДНУ статью, которая лучше всего
   подходит для проверки данного тезиса.

2. Сравнить тезис с этой статьёй.

Варианты результата:

SUPPORTED
- статья непосредственно подтверждает тезис.

PARTIALLY_SUPPORTED
- основная идея поддерживается, но тезис сформулирован
  слишком широко, слишком категорично или содержит
  конкретизацию, которой в исследовании нет.

CONTRADICTED
- результаты выбранной статьи противоречат тезису.

INSUFFICIENT_EVIDENCE
- статья не дает достаточно данных, чтобы подтвердить
  или опровергнуть тезис.

Очень важные правила:

- Используй ТОЛЬКО переданные данные статей.
- Не используй собственные знания вместо данных PubMed.
- Не придумывай факты, статистику или PMID.
- Не выдавай корреляцию за причинно-следственную связь.
- Не распространяй результаты исследования на всех людей,
  если исследование изучало конкретную группу.
- Учитывай популяцию, вмешательство, результат и тип исследования.
- Если статья не подтверждает точную формулировку тезиса,
  используй PARTIALLY_SUPPORTED или INSUFFICIENT_EVIDENCE.

--------------------------------------------------
ЯЗЫК
--------------------------------------------------

ВАЖНО:

- claim может быть на русском или английском;
- reason ОБЯЗАТЕЛЬНО пиши на русском языке;
- article_title_ru ОБЯЗАТЕЛЬНО пиши на русском языке;
- не оставляй английских предложений в reason;
- не добавляй никаких пояснений вне JSON.

--------------------------------------------------
ПЕРЕВОД НАЗВАНИЯ
--------------------------------------------------

Возьми оригинальное название выбранной статьи
из переданных данных и переведи его на русский.

Перевод должен:
- максимально точно передавать смысл оригинала;
- сохранять научную терминологию;
- не добавлять информацию, которой нет в оригинале;
- не превращать название в рекламный заголовок.

--------------------------------------------------
ФОРМАТ
--------------------------------------------------

Верни ТОЛЬКО корректный JSON:

{
  "best_pmid": "12345678",
  "article_title_ru": "Русское название исследования",
  "verdict": "SUPPORTED",
  "reason": "Короткий вывод на русском языке."
}
""".strip()

        # --------------------------------------------------
        # USER PROMPT
        # --------------------------------------------------

        user_prompt = f"""
НАУЧНЫЙ ТЕЗИС:

{claim}


КАНДИДАТНЫЕ СТАТЬИ PUBMED:

{articles_json}
""".strip()

        # --------------------------------------------------
        # QWEN
        # --------------------------------------------------

        response = await client.chat.completions.create(
            model=MODEL_NAME,
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
            temperature=0,
        )

        content = (
            response.choices[0]
            .message
            .content
        )

        if not content:
            raise RuntimeError(
                "Qwen returned an empty fact-check response"
            )

        result = _extract_json(
            content
        )

        if not isinstance(
            result,
            dict,
        ):
            raise RuntimeError(
                "Fact-check response must be a JSON object"
            )

        best_pmid = result.get(
            "best_pmid"
        )

        article_title_ru = result.get(
            "article_title_ru"
        )

        verdict = result.get(
            "verdict"
        )

        reason = result.get(
            "reason"
        )

        # --------------------------------------------------
        # Проверяем verdict
        # --------------------------------------------------

        allowed_verdicts = {
            "SUPPORTED",
            "PARTIALLY_SUPPORTED",
            "CONTRADICTED",
            "INSUFFICIENT_EVIDENCE",
        }

        if (
            verdict
            not in allowed_verdicts
        ):
            raise RuntimeError(
                f"Invalid verdict from Qwen: "
                f"{verdict}"
            )

        if not isinstance(
            reason,
            str,
        ):
            reason = ""

        if not isinstance(
            article_title_ru,
            str,
        ):
            article_title_ru = ""

        # --------------------------------------------------
        # Проверяем PMID
        # --------------------------------------------------

        valid_pmids = {
            str(
                article.get("pmid")
            )
            for article in articles
            if article.get("pmid")
        }

        if (
            best_pmid is not None
            and str(best_pmid)
            not in valid_pmids
        ):
            best_pmid = None

            verdict = (
                "INSUFFICIENT_EVIDENCE"
            )

            reason = (
                "Модель не смогла выбрать "
                "корректную статью из найденных."
            )

            article_title_ru = ""

        results.append(
            {
                "claim": claim,
                "verdict": verdict,
                "reason": reason.strip(),
                "best_pmid": (
                    str(best_pmid)
                    if best_pmid
                    else None
                ),
                "article_title_ru": (
                    article_title_ru.strip()
                ),
                "articles": articles,
            }
        )

    return results


# ==========================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ==========================================================

async def check_post(
    post: str,
) -> dict:
    """
    Главная функция проверки готового поста.

    Внешнему коду достаточно:

        result = await check_post(post)

    Внутри происходит:

        Пост
          ↓
        Qwen
          ↓
        научные тезисы
          ↓
        PubMed
          ↓
        статьи
          ↓
        Qwen
          ↓
        лучшая статья + вердикт
    """

    post = post.strip()

    if not post:
        raise ValueError(
            "Post cannot be empty"
        )

    client = _get_client()

    # --------------------------------------------------
    # 1. Выделяем научные тезисы
    # --------------------------------------------------

    print(
        "\nВыделяю научные тезисы..."
    )

    claims = await _extract_claims(
        client=client,
        post=post,
    )

    if not claims:
        return {
            "overall_verdict": "OK",
            "claims": [],
            "summary": (
                "В посте не найдено "
                "научно проверяемых утверждений."
            ),
        }

    # --------------------------------------------------
    # 2. Ищем статьи в PubMed
    # --------------------------------------------------

    print(
        "\nИщу научные статьи в PubMed..."
    )

    evidence = await _collect_evidence(
        claims
    )

    # --------------------------------------------------
    # 3. Проверяем тезисы
    # --------------------------------------------------

    print(
        "\nПроверяю тезисы по найденным статьям..."
    )

    checked_claims = await _check_evidence(
        client=client,
        evidence=evidence,
    )

    # --------------------------------------------------
    # 4. Формируем компактный результат
    # --------------------------------------------------

    final_claims = []

    for claim_result in checked_claims:

        best_pmid = claim_result.get(
            "best_pmid"
        )

        best_article = None

        # Ищем реальную статью,
        # которую выбрал Qwen.
        for article in claim_result.get(
            "articles",
            [],
        ):

            if str(
                article.get("pmid")
            ) == str(best_pmid):

                best_article = article
                break

        # Ссылку формируем сами
        # по реальному PMID.
        source = None

        if best_pmid:
            source = (
                "https://pubmed.ncbi.nlm.nih.gov/"
                f"{best_pmid}/"
            )

        # Если Qwen не смог перевести название,
        # используем оригинальное название из PubMed
        # как запасной вариант.
        article_title = (
            claim_result.get(
                "article_title_ru"
            )
            or (
                best_article.get(
                    "title"
                )
                if best_article
                else None
            )
        )

        final_claims.append(
            {
                "claim": claim_result[
                    "claim"
                ],
                "verdict": claim_result[
                    "verdict"
                ],
                "reason": claim_result[
                    "reason"
                ],
                "article": article_title,
                "pmid": best_pmid,
                "source": source,
            }
        )

    # --------------------------------------------------
    # 5. Общий результат
    # --------------------------------------------------

    verdicts = {
        claim["verdict"]
        for claim in final_claims
    }

    if verdicts.intersection(
        {
            "PARTIALLY_SUPPORTED",
            "CONTRADICTED",
            "INSUFFICIENT_EVIDENCE",
        }
    ):
        overall_verdict = (
            "NEEDS_REVISION"
        )
    else:
        overall_verdict = "OK"

    return {
        "overall_verdict": overall_verdict,
        "claims": final_claims,
    }
