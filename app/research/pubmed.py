import os
import xml.etree.ElementTree as ET

import httpx
from dotenv import load_dotenv


# ==========================================================
# CONFIGURATION
# ==========================================================

# Загружаем переменные из .env.
#
# В .env должны находиться:
#
# NCBI_API_KEY=...
# NCBI_EMAIL=...
#
# API key мы никогда не храним непосредственно в коде.
load_dotenv()


# Официальный endpoint NCBI ESearch.
#
# ESearch используется для поиска статей.
PUBMED_SEARCH_URL = (
    "https://eutils.ncbi.nlm.nih.gov"
    "/entrez/eutils/esearch.fcgi"
)


# Официальный endpoint NCBI EFetch.
#
# EFetch используется для получения самих записей
# найденных статей.
PUBMED_FETCH_URL = (
    "https://eutils.ncbi.nlm.nih.gov"
    "/entrez/eutils/efetch.fcgi"
)


# ==========================================================
# NCBI SETTINGS
# ==========================================================

def _get_ncbi_settings() -> tuple[str, str]:
    """
    Получает настройки NCBI из переменных окружения.

    Возвращает:

        (
            api_key,
            email,
        )

    Почему отдельная функция?

    Потому что и ESearch, и EFetch используют
    одинаковые настройки.

    Так мы не дублируем один и тот же код.
    """

    api_key = os.getenv("NCBI_API_KEY")
    email = os.getenv("NCBI_EMAIL")

    if not api_key:
        raise RuntimeError(
            "NCBI_API_KEY is not set"
        )

    if not email:
        raise RuntimeError(
            "NCBI_EMAIL is not set"
        )

    return api_key, email


# ==========================================================
# PUBMED SEARCH
# ==========================================================

async def search_pubmed(
    query: str,
    max_results: int = 10,
) -> list[str]:
    """
    Ищет научные статьи в PubMed.

    Например:

        query =
            "high protein diet muscle mass weight loss"

    Результат:

        [
            "42701496",
            "42514348",
            "42472055",
        ]

    ВАЖНО:

    Эта функция возвращает только PMID.

    Полную информацию об этих статьях
    получаем отдельно через EFetch.
    """

    # Получаем API key и email.
    api_key, email = _get_ncbi_settings()

    # Убираем пробелы по краям.
    query = query.strip()

    if not query:
        raise ValueError(
            "PubMed search query cannot be empty"
        )

    if max_results <= 0:
        raise ValueError(
            "max_results must be greater than 0"
        )

    # Параметры запроса ESearch.
    params = {
        # Говорим NCBI, что ищем именно в PubMed.
        "db": "pubmed",

        # Сам поисковый запрос.
        "term": query,

        # Максимальное количество результатов.
        "retmax": max_results,

        # Просим JSON вместо XML.
        #
        # Для ESearch это удобно,
        # потому что нам нужен только список PMID.
        "retmode": "json",

        # API key NCBI.
        "api_key": api_key,

        # Email разработчика.
        "email": email,

        # Название нашего приложения.
        "tool": "ContentOps",
    }

    # Создаем асинхронный HTTP-клиент.
    #
    # AsyncClient хорошо подходит нашему проекту,
    # потому что Telegram bot, Apify и OpenRouter
    # у нас тоже работают асинхронно.
    async with httpx.AsyncClient(
        timeout=30.0
    ) as client:

        # Отправляем GET-запрос.
        response = await client.get(
            PUBMED_SEARCH_URL,
            params=params,
        )

        # Если HTTP статус плохой,
        # например 400 / 429 / 500,
        # здесь будет выброшено исключение.
        response.raise_for_status()

        # Преобразуем JSON в Python dict.
        data = response.json()

    # Получаем блок esearchresult.
    search_result = data.get(
        "esearchresult",
        {},
    )

    # Из него достаем список PMID.
    pmids = search_result.get(
        "idlist",
        [],
    )

    # Проверяем, что API вернул список.
    if not isinstance(pmids, list):
        raise RuntimeError(
            "Unexpected PubMed API response: "
            "idlist is not a list"
        )

    return pmids


# ==========================================================
# PUBMED ARTICLE FETCH
# ==========================================================

async def fetch_pubmed_articles(
    pmids: list[str],
) -> list[dict]:
    """
    Получает информацию о статьях по PMID.

    Например:

        [
            "42701496",
            "42514348",
            "42472055",
        ]

    превращается примерно в:

        [
            {
                "pmid": "...",
                "title": "...",
                "abstract": "...",
                "authors": [...],
                "journal": "...",
                "publication_types": [...],
                "publication_date": "...",
                "doi": "...",
                "pmc_id": "..."
            }
        ]

    Сейчас мы не получаем full text статьи.

    Мы получаем metadata + abstract
    и дополнительно проверяем наличие PMCID.
    """

    # Если PMID нет,
    # HTTP-запрос делать бессмысленно.
    if not pmids:
        return []

    api_key, email = _get_ncbi_settings()

    # Приводим все PMID к строкам.
    #
    # Это защищает нас от ситуации:
    #
    # [42701496, 42514348]
    #
    # и превращает ее в:
    #
    # ["42701496", "42514348"]
    normalized_pmids = [
        str(pmid).strip()
        for pmid in pmids
        if str(pmid).strip()
    ]

    if not normalized_pmids:
        return []

    # EFetch принимает несколько ID через запятую.
    #
    # Получится:
    #
    # id=42701496,42514348,42472055
    ids = ",".join(normalized_pmids)

    params = {
        "db": "pubmed",
        "id": ids,

        # Для PubMed используем XML,
        # потому что XML содержит структурированные
        # элементы статьи.
        "retmode": "xml",

        "api_key": api_key,
        "email": email,
        "tool": "ContentOps",
    }

    async with httpx.AsyncClient(
        timeout=30.0
    ) as client:

        # Получаем записи статей.
        response = await client.get(
            PUBMED_FETCH_URL,
            params=params,
        )

        response.raise_for_status()

        # EFetch возвращает XML.
        xml_text = response.text

    # ------------------------------------------------------
    # PARSE XML
    # ------------------------------------------------------

    # Превращаем XML-текст
    # в дерево элементов Python.
    root = ET.fromstring(xml_text)

    articles = []

    # В XML каждая статья представлена
    # отдельным <PubmedArticle>.
    for article in root.findall(
        ".//PubmedArticle"
    ):

        # ==================================================
        # PMID
        # ==================================================

        pmid_element = article.find(
            ".//PMID"
        )

        pmid = (
            pmid_element.text.strip()
            if (
                pmid_element is not None
                and pmid_element.text
            )
            else None
        )

        # ==================================================
        # TITLE
        # ==================================================

        title_element = article.find(
            ".//ArticleTitle"
        )

        # ArticleTitle иногда содержит
        # не только обычный текст,
        # но и вложенные XML-элементы.

        title = (
            "".join(
                title_element.itertext()
            ).strip()
            if title_element is not None
            else ""
        )

        # ==================================================
        # ABSTRACT
        # ==================================================

        abstract_parts = []

        # Abstract может состоять из нескольких секций:
        #
        # BACKGROUND
        # METHODS
        # RESULTS
        # CONCLUSIONS
        #
        # Поэтому собираем их отдельно.
        for abstract_text in article.findall(
            ".//Abstract/AbstractText"
        ):

            # Например:
            #
            # <AbstractText Label="RESULTS">
            #
            # Тогда label = "RESULTS".
            label = abstract_text.get(
                "Label"
            )

            text = "".join(
                abstract_text.itertext()
            ).strip()

            if not text:
                continue

            if label:
                abstract_parts.append(
                    f"{label}: {text}"
                )
            else:
                abstract_parts.append(
                    text
                )

        abstract = "\n\n".join(
            abstract_parts
        )

        # ==================================================
        # JOURNAL
        # ==================================================

        journal_element = article.find(
            ".//Journal/Title"
        )

        journal = (
            journal_element.text.strip()
            if (
                journal_element is not None
                and journal_element.text
            )
            else ""
        )

        # ==================================================
        # PUBLICATION DATE
        # ==================================================

        pub_date = article.find(
            ".//PubDate"
        )

        publication_date_parts = []

        if pub_date is not None:

            year = pub_date.findtext(
                "Year"
            )

            month = pub_date.findtext(
                "Month"
            )

            day = pub_date.findtext(
                "Day"
            )

            if year:
                publication_date_parts.append(
                    year
                )

            if month:
                publication_date_parts.append(
                    month
                )

            if day:
                publication_date_parts.append(
                    day
                )

        publication_date = " ".join(
            publication_date_parts
        )

        # ==================================================
        # AUTHORS
        # ==================================================

        authors = []

        for author in article.findall(
            ".//AuthorList/Author"
        ):

            # Обычный автор.
            lastname = author.findtext(
                "LastName"
            )

            initials = author.findtext(
                "Initials"
            )

            # Иногда автором выступает
            # целая исследовательская группа.
            collective_name = (
                author.findtext(
                    "CollectiveName"
                )
            )

            if collective_name:
                authors.append(
                    collective_name.strip()
                )
                continue

            parts = []

            if lastname:
                parts.append(
                    lastname.strip()
                )

            if initials:
                parts.append(
                    initials.strip()
                )

            if parts:
                authors.append(
                    " ".join(parts)
                )

        # ==================================================
        # PUBLICATION TYPES
        # ==================================================

        publication_types = []

        # Примеры:
        #
        # Journal Article
        # Randomized Controlled Trial
        # Meta-Analysis
        # Systematic Review
        #
        # Для будущего fact-checker это очень
        # важное поле.
        for pub_type in article.findall(
            ".//PublicationTypeList/PublicationType"
        ):

            if pub_type.text:
                publication_types.append(
                    pub_type.text.strip()
                )

        # ==================================================
        # DOI + PMCID
        # ==================================================

        # PubMed хранит дополнительные идентификаторы
        # в ArticleIdList.
        #
        # Например:
        #
        # DOI
        # PubMed Central ID
        # другие идентификаторы издателя.
        doi = None
        pmc_id = None

        for article_id in article.findall(
            ".//PubmedData/ArticleIdList/ArticleId"
        ):

            id_type = article_id.get(
                "IdType"
            )

            if not article_id.text:
                continue

            identifier = (
                article_id.text.strip()
            )

            # DOI.
            if id_type == "doi":
                doi = identifier

            # PMCID.
            #
            # В зависимости от XML/версии данных
            # можно встретить идентификатор PMC.
            elif id_type == "pmc":
                pmc_id = identifier

        # ==================================================
        # СОБИРАЕМ СТАТЬЮ
        # ==================================================

        articles.append(
            {
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "journal": journal,
                "publication_types": (
                    publication_types
                ),
                "publication_date": (
                    publication_date
                ),
                "doi": doi,
                "pmc_id": pmc_id,
            }
        )

    return articles


# ==========================================================
# SEARCH + FETCH
# ==========================================================

async def search_and_fetch_pubmed(
    query: str,
    max_results: int = 5,
) -> list[dict]:
    """
    Полный поиск статей.

    Шаг 1:
        ESearch

        query
          ↓
        PMID

    Шаг 2:
        EFetch

        PMID
          ↓
        article metadata + abstract + PMCID

    Поэтому остальному приложению
    не нужно знать внутреннюю механику PubMed.

    Оно просто вызывает:

        articles = await search_and_fetch_pubmed(...)
    """

    # Ищем PMID.
    pmids = await search_pubmed(
        query=query,
        max_results=max_results,
    )

    # Если статей нет,
    # второй запрос делать не нужно.
    if not pmids:
        return []

    # Получаем статьи.
    return await fetch_pubmed_articles(
        pmids
    )
