from app.research.post_reviser import (
    build_pubmed_supplement_fallback,
    build_revised_pubmed_fallback,
)


FACT_CHECK = {
    "claims": [
        {
            "claim": "Силовые тренировки улучшают мышечную силу",
            "verdict": "SUPPORTED",
            "pmid": "12345678",
        },
        {
            "claim": "Добавка сжигает жир после тренировки",
            "verdict": "PARTIALLY_SUPPORTED",
            "reason": "Добавка может поддерживать восстановление после тренировки.",
            "pmid": "87654321",
        },
        {
            "claim": "Добавка сжигает жир без усилий",
            "verdict": "INSUFFICIENT_EVIDENCE",
            "pmid": None,
        },
    ]
}


def test_pubmed_supplement_updates_partial_but_keeps_other_claims():
    post = (
        "Силовые тренировки улучшают мышечную силу. "
        "Добавка сжигает жир после тренировки. "
        "Добавка сжигает жир без усилий."
    )

    result = build_pubmed_supplement_fallback(post, FACT_CHECK)

    assert result == (
        "Силовые тренировки улучшают мышечную силу. (PMID: 12345678) "
        "Добавка может поддерживать восстановление после тренировки. "
        "(PMID: 87654321) "
        "Добавка сжигает жир без усилий."
    )


def test_strict_pubmed_revision_keeps_supported_and_corrected_partial_claims():
    post = (
        "Силовые тренировки улучшают мышечную силу. "
        "Добавка сжигает жир после тренировки. "
        "Добавка сжигает жир без усилий."
    )

    result = build_revised_pubmed_fallback(post, FACT_CHECK)

    assert result == (
        "Силовые тренировки улучшают мышечную силу. (PMID: 12345678)\n\n"
        "Добавка может поддерживать восстановление после тренировки. "
        "(PMID: 87654321)"
    )


def test_fallback_uses_the_best_matching_claim_not_the_first_similar_one():
    fact_check = {
        "claims": [
            {
                "claim": "Силовые тренировки повышают силу у пожилых людей",
                "verdict": "SUPPORTED",
                "pmid": "111",
            },
            {
                "claim": "Силовые тренировки повышают силу у подростков",
                "verdict": "SUPPORTED",
                "pmid": "222",
            },
        ]
    }

    result = build_pubmed_supplement_fallback(
        "Силовые тренировки повышают силу у подростков.",
        fact_check,
    )

    assert result.endswith("(PMID: 222)")
