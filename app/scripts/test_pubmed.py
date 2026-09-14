import asyncio

from app.research.pubmed import (
    search_and_fetch_pubmed,
)


async def main():
    # Выполняем полноценный поиск:
    #
    # 1. Отправляем запрос в PubMed через ESearch.
    # 2. Получаем PMID найденных статей.
    # 3. Передаем PMID в EFetch.
    # 4. Получаем данные самих статей.
    articles = await search_and_fetch_pubmed(
        query=(
            "high protein diet "
            "muscle mass weight loss"
        ),
        max_results=5,
    )

    print(
        f"\nFound articles: {len(articles)}\n"
    )

    # Выводим найденные статьи по очереди.
    for index, article in enumerate(
        articles,
        start=1,
    ):
        print("=" * 80)

        print(
            f"ARTICLE #{index}"
        )

        # Уникальный идентификатор статьи в PubMed.
        print(
            f"PMID: "
            f"{article['pmid']}"
        )

        # Если статья присутствует в PubMed Central,
        # здесь будет ее PMCID.
        #
        # Если записи в PMC нет:
        # N/A
        print(
            f"PMC ID: "
            f"{article['pmc_id'] or 'N/A'}"
        )

        # Название научной статьи.
        print(
            f"Title: "
            f"{article['title']}"
        )

        # Научный журнал.
        print(
            f"Journal: "
            f"{article['journal']}"
        )

        # Дата публикации.
        print(
            f"Date: "
            f"{article['publication_date']}"
        )

        # Показываем первых пяти авторов,
        # чтобы терминал не превращался
        # в огромный список.
        authors = article["authors"][:5]

        print(
            "Authors: "
            f"{', '.join(authors)}"
        )

        # Тип исследования / публикации.
        #
        # Например:
        # Randomized Controlled Trial
        # Meta-Analysis
        # Systematic Review
        print(
            "Publication types: "
            f"{', '.join(article['publication_types'])}"
        )

        # DOI статьи.
        #
        # Если DOI отсутствует:
        # N/A
        print(
            f"DOI: "
            f"{article['doi'] or 'N/A'}"
        )

        # Abstract.
        #
        # Именно этот текст впоследствии будет
        # одним из основных источников evidence
        # для нашего fact-checker.
        print(
            "\nABSTRACT:\n"
        )

        print(
            article["abstract"]
            or "Abstract unavailable"
        )

        print()


# Точка входа программы.
#
# asyncio.run() запускает наш async main()
# и создает event loop, необходимый
# для работы async/await.
if __name__ == "__main__":
    asyncio.run(main())
