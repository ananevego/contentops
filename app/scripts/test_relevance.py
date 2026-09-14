import asyncio

from app.research.pubmed import (
    search_and_fetch_pubmed,
)
from app.research.relevance import (
    analyze_relevance,
)


async def main():
    # --------------------------------------------------
    # 1. Наш научный claim
    # --------------------------------------------------
    #
    # Это именно то утверждение,
    # которое в будущем будет извлекаться
    # из готового Telegram-поста.
    claim = (
        "Higher protein intake helps preserve "
        "muscle mass during weight loss."
    )

    print(
        "CLAIM:\n"
    )

    print(claim)

    print(
        "\nSearching PubMed..."
    )

    # --------------------------------------------------
    # 2. Ищем статьи
    # --------------------------------------------------

    articles = await search_and_fetch_pubmed(
        query=(
            "high protein diet "
            "muscle mass weight loss"
        ),
        max_results=5,
    )

    print(
        f"Found articles: "
        f"{len(articles)}"
    )

    # --------------------------------------------------
    # 3. Передаем статьи Qwen
    # --------------------------------------------------

    print(
        "\nAnalyzing relevance with Qwen..."
    )

    results = await analyze_relevance(
        claim=claim,
        articles=articles,
    )

    # --------------------------------------------------
    # 4. Показываем результат
    # --------------------------------------------------

    print(
        "\n"
        + "=" * 80
    )

    print(
        "RELEVANCE RESULTS"
    )

    print(
        "=" * 80
    )

    for result in results:

        print(
            f"\nPMID: "
            f"{result['pmid']}"
        )

        print(
            f"Relevance: "
            f"{result['relevance']}"
        )

        print(
            f"Reason: "
            f"{result['reason']}"
        )


if __name__ == "__main__":
    asyncio.run(main())
