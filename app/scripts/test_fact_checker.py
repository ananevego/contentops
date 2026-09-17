import asyncio

from app.research.fact_checker import (
    check_post,
)


def format_verdict(
    verdict: str,
) -> str:
    """
    Переводит внутренний технический статус
    в нормальный русский текст.
    """

    verdicts = {
        "SUPPORTED": (
            "✅ Подтверждается"
        ),
        "PARTIALLY_SUPPORTED": (
            "⚠️ Частично подтверждается"
        ),
        "CONTRADICTED": (
            "❌ Не подтверждается"
        ),
        "INSUFFICIENT_EVIDENCE": (
            "❓ Недостаточно данных"
        ),
    }

    return verdicts.get(
        verdict,
        "❓ Не удалось определить",
    )


async def main():

    post = """
Высокобелковая диета помогает сохранить мышечную массу
во время похудения. Поэтому при снижении веса стоит
есть около 2 г белка на кг массы тела.

Также считается, что увеличение потребления белка
ускоряет метаболизм и помогает быстрее сжигать жир.
"""

    print(
        "\n"
        + "=" * 80
    )

    print(
        "🔬 ПРОВЕРКА ПОСТА ПО PUBMED"
    )

    print(
        "=" * 80
    )

    print(post)

    # Запускаем нашего Fact Checker.
    result = await check_post(
        post
    )

    print(
        "\n"
        + "=" * 80
    )

    print(
        "РЕЗУЛЬТАТ ПРОВЕРКИ"
    )

    print(
        "=" * 80
    )

    # Проходим по каждому найденному тезису.
    for index, claim in enumerate(
        result["claims"],
        start=1,
    ):

        print(
            f"\n{index}. "
            f"{claim['claim']}"
        )

        # Русская формулировка verdict.
        print(
            f"\n"
            f"{format_verdict(claim['verdict'])}"
        )

        # Показываем наиболее подходящее
        # научное исследование.
        if claim["article"]:

            print(
                "\n📚 Наиболее подходящее исследование:"
            )

            print(
                claim["article"]
            )

            print(
                f"PMID: "
                f"{claim['pmid']}"
            )

            print(
                f"🔗 PubMed: "
                f"{claim['source']}"
            )

        # Краткий вывод Qwen.
        print(
            "\n💬 Вывод:"
        )

        print(
            claim["reason"]
        )

        print(
            "\n"
            + "-" * 80
        )

    # Общий статус также переводим на русский.
    if (
        result["overall_verdict"]
        == "OK"
    ):
        overall_text = (
            "✅ Существенных проблем не найдено"
        )
    else:
        overall_text = (
            "⚠️ В посте есть утверждения, "
            "которые требуют уточнения"
        )

    print(
        "\n"
        f"Общий результат: "
        f"{overall_text}"
    )


if __name__ == "__main__":
    asyncio.run(main())
