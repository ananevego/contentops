from app.research.post_reviser import (
    build_pubmed_supplement_fallback,
    build_supported_only_fallback,
)


FACT_CHECK = {
    "claims": [
        {
            "claim": "Силовые тренировки улучшают мышечную силу",
            "verdict": "SUPPORTED",
            "pmid": "12345678",
        },
        {
            "claim": "Добавка сжигает жир без усилий",
            "verdict": "INSUFFICIENT_EVIDENCE",
            "pmid": None,
        },
    ]
}


def test_pubmed_supplement_keeps_unconfirmed_claims_unchanged():
    post = (
        "Силовые тренировки улучшают мышечную силу. "
        "Добавка сжигает жир без усилий."
    )

    result = build_pubmed_supplement_fallback(post, FACT_CHECK)

    assert result == (
        "Силовые тренировки улучшают мышечную силу. (PMID: 12345678) "
        "Добавка сжигает жир без усилий."
    )


def test_supported_only_pubmed_removes_unconfirmed_claims():
    post = (
        "Силовые тренировки улучшают мышечную силу. "
        "Добавка сжигает жир без усилий."
    )

    result = build_supported_only_fallback(post, FACT_CHECK)

    assert result == "Силовые тренировки улучшают мышечную силу. (PMID: 12345678)"
