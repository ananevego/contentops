import json
import os
import re

from dotenv import load_dotenv
from openai import AsyncOpenAI

from app.research.pubmed import (
    search_and_fetch_pubmed,
)
from app.research.relevance import analyze_relevance


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

def _remove_invalid_json_escapes(text: str) -> str:
    """Убирает только обратные слэши, которые недопустимы в JSON.

    Некоторые модели ставят обратный слэш перед ``[Title/Abstract]``.
    В JSON это невалидная escape-последовательность, хотя в самом поисковом
    запросе слэши не нужны. Валидные JSON-экранирования (например, ``\\n``
    и ``\\\"``) не изменяются.
    """
    return re.sub(r'\\(?!["\\\\/bfnrtu])', "", text)


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
        # Qwen иногда экранирует квадратные скобки в field tags PubMed.
        # Повторяем разбор только после узкой нормализации невалидных escape.
        repaired_text = _remove_invalid_json_escapes(text)
        if repaired_text != text:
            try:
                return json.loads(repaired_text)
            except json.JSONDecodeError:
                pass

        raise RuntimeError(
            "Qwen returned invalid JSON:\n"
            f"{text}"
        ) from exc


def _recover_claims_from_malformed_json(text: str) -> list[dict]:
    """Извлекает тезисы из типичного ответа модели с кавычками в query.

    Это не универсальный JSON-парсер: используется только как запасной путь
    для списка ``claim/search_query``, когда модель забыла экранировать
    кавычки внутри PubMed field tags.
    """
    recovered = []
    for object_text in re.findall(r"\{(.*?)\}", text, flags=re.DOTALL):
        claim_match = re.search(
            r'"claim"\s*:\s*"(.*?)"\s*,\s*"search_query"',
            object_text,
            flags=re.DOTALL,
        )
        query_match = re.search(
            r'"search_query"\s*:\s*"(.*)"\s*$',
            object_text,
            flags=re.DOTALL,
        )
        if claim_match and query_match:
            recovered.append(
                {
                    "claim": claim_match.group(1),
                    "search_query": query_match.group(1),
                }
            )
    return recovered


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
2. search_query — точный поисковый запрос для PubMed.

Правила:
- Не придумывай утверждения, которых нет в посте.
- Не меняй смысл исходного утверждения.
- Сохраняй формулировку как можно ближе к исходному тексту.
- Один объект — один атомарный тезис. Не объединяй в один тезис
  несколько разных причин, эффектов или рекомендаций.
- Максимум 5 утверждений.

Обычный текст пиши на русском языке.

search_query ОБЯЗАТЕЛЬНО составляй на английском языке. Включи в него
все ключевые части тезиса: популяцию/контекст, воздействие или упражнение
и измеряемый результат. Используй точные фразы и поля PubMed [Title/Abstract]
с AND/OR, например:
resistance training[Title/Abstract] AND training to failure[Title/Abstract]
AND (strength[Title/Abstract] OR hypertrophy[Title/Abstract])

Внутри search_query НИКОГДА не используй символ двойной кавычки (").
Он не нужен для PubMed и может сделать JSON невалидным.

Не ищи по одной аббревиатуре или общему слову. Всегда расшифровывай
аббревиатуру и добавляй контекст: для RIR используй "repetitions in reserve"
вместе с "resistance training". Запрос "RIR" сам по себе запрещён, потому что
в PubMed он имеет другие значения. Не подменяй тему тезиса соседней темой.

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

    try:
        data = _extract_json(content)
    except RuntimeError as error:
        data = _recover_claims_from_malformed_json(content)
        if not data:
            raise error

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

MAX_PUBMED_QUERIES = 5
MAX_CANDIDATE_ARTICLES = 25


def _build_pubmed_queries(search_query: str) -> list[str]:
    """Returns a precise query and a bounded set of recall-oriented fallbacks.

    Модель иногда добавляет в первичный запрос вывод тезиса
    («сохранение техники», «цена ошибки»), который не обязан встречаться в
    названии или аннотации исследования. Поэтому для КАЖДОГО запроса строится
    версия без ограничения только title/abstract. Если она всё ещё слишком
    строгая, ищем по каждой паре понятий, а не только по первым двум: outcome
    часто стоит в конце запроса и иначе теряется.

    RIR — пример неоднозначной аббревиатуры в PubMed (в том числе
    inflammatory risk), поэтому словарь расшифровок не позволяет искать по
    ней в одиночку.
    """
    normalized_query = re.sub(
        r"\bRIR\b",
        '"repetitions in reserve"',
        search_query,
        flags=re.IGNORECASE,
    )
    # Непарные кавычки встречаются в частично повреждённом ответе модели и
    # делают запрос невалидным. Корректные пары сохраняем: они нужны PubMed
    # для точного поиска многословных терминов.
    if normalized_query.count('"') % 2:
        normalized_query = normalized_query.replace('"', "")
    queries = [normalized_query]
    untagged_query = re.sub(
        r"\[Title/Abstract\]",
        "",
        normalized_query,
        flags=re.IGNORECASE,
    )
    concepts = [
        concept.strip(" ()")
        for concept in re.split(r"\s+AND\s+", untagged_query, flags=re.IGNORECASE)
        if concept.strip(" ()")
    ]
    if untagged_query.strip():
        queries.append(untagged_query.strip())

    for first_index, first_concept in enumerate(concepts):
        for second_concept in concepts[first_index + 1:]:
            broad_query = f"{first_concept} AND {second_concept}"
            if (
                '"repetitions in reserve"' in broad_query.casefold()
                and "resistance training" not in broad_query.casefold()
            ):
                broad_query = f'"resistance training" AND ({broad_query})'
            queries.append(broad_query)

            if len(dict.fromkeys(queries)) >= MAX_PUBMED_QUERIES:
                return list(dict.fromkeys(queries))[:MAX_PUBMED_QUERIES]

    return list(dict.fromkeys(queries))[:MAX_PUBMED_QUERIES]


async def _collect_evidence(
    claims: list[dict],
) -> list[dict]:
    """
    Для каждого научного тезиса делает поиск в PubMed.

    PubMed возвращает кандидатов, затем отдельный этап релевантности
    исключает статьи, которые совпали только по ключевому слову.
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

        # Сначала выполняем точный запрос, затем широкий тематический
        # запрос. Он не подменяет тезис выводом: выбор и вердикт по-прежнему
        # делают только по фактической статье ниже.
        articles_by_pmid = {}
        for query_index, query in enumerate(
            _build_pubmed_queries(search_query),
        ):
            articles = await search_and_fetch_pubmed(
                query=query,
                max_results=10 if query_index == 0 else 5,
            )
            for article in articles:
                pmid = article.get("pmid")
                if pmid:
                    articles_by_pmid[str(pmid)] = article

                if len(articles_by_pmid) >= MAX_CANDIDATE_ARTICLES:
                    break

            if len(articles_by_pmid) >= MAX_CANDIDATE_ARTICLES:
                break

        articles = list(articles_by_pmid.values())

        # Не позволяем статье с совпавшей аббревиатурой попасть в этап
        # фактчекинга. Например, RIR в кардиологической статье — не RIR
        # (repetitions in reserve) из поста о силовых тренировках.
        relevance = await analyze_relevance(
            claim=claim,
            articles=articles,
        ) if articles else []
        relevant_pmids = {
            result["pmid"]
            for result in relevance
            if result["relevance"] == "RELEVANT"
        }
        # Классификатор релевантности — защитный слой, но не источник истины.
        # Если он ошибочно отверг все статьи, передаём кандидатов фактчекеру:
        # тот обязан вернуть INSUFFICIENT_EVIDENCE, если ни одна статья не
        # проверяет точную формулировку, вместо ложного «ничего не найдено».
        if relevant_pmids:
            articles = [
                article
                for article in articles
                if str(article.get("pmid")) in relevant_pmids
            ]

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
                        "Среди найденных в PubMed статей нет исследований, "
                        "релевантных точной формулировке тезиса."
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
- Кандидаты найдены тематическими запросами, но среди них могут быть статьи
  с более широкой или соседней темой. Не выбирай PMID, если статья не изучает
  именно популяцию, воздействие и результат из тезиса.
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

        # Подтверждающий вердикт без выбранной статьи нельзя показать
        # пользователю и нельзя считать доказательством.
        if not best_pmid and verdict != "INSUFFICIENT_EVIDENCE":
            verdict = "INSUFFICIENT_EVIDENCE"
            reason = (
                "Не выбрана релевантная статья PubMed, поэтому тезис "
                "нельзя оценить по найденным данным."
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
