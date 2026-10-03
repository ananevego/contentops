"""Regression tests for keeping keyword-only PubMed hits out of fact checks."""

import unittest
from unittest.mock import AsyncMock, patch

from app.research.fact_checker import (
    _build_pubmed_queries,
    _collect_evidence,
    _extract_json,
    _recover_claims_from_malformed_json,
)


class FactCheckerRelevanceTests(unittest.IsolatedAsyncioTestCase):
    def test_extract_json_repairs_invalid_pubmed_field_tag_escaping(self):
        result = _extract_json(
            r'''[{"search_query": "\"resistance training\"\[Title/Abstract\]"}]'''
        )
        self.assertEqual(
            result[0]["search_query"],
            '"resistance training"[Title/Abstract]',
        )

    def test_query_is_expanded_with_a_generic_broader_fallback(self):
        queries = _build_pubmed_queries(
            'creatine[Title/Abstract] AND "resistance training"[Title/Abstract] AND strength[Title/Abstract]'
        )

        self.assertIn("creatine", queries[1])
        self.assertIn('"resistance training"', queries[1])
        self.assertNotIn("Title/Abstract", queries[1])
        self.assertIn(
            '"resistance training" AND strength',
            queries,
        )

    def test_rir_is_expanded_before_searching(self):
        queries = _build_pubmed_queries('RIR[Title/Abstract] AND fatigue[Title/Abstract]')

        self.assertNotIn("RIR[", queries[0])
        self.assertIn('"repetitions in reserve"', queries[0])
        self.assertTrue(
            any('"resistance training"' in query for query in queries[1:])
        )

    def test_recovers_claims_with_unescaped_quotes_in_query(self):
        recovered = _recover_claims_from_malformed_json(
            '''[
              {
                "claim": "Короткие тренировки стимулируют синтез белка.",
                "search_query": "(short exercise sessions"[Title/Abstract] AND protein synthesis[Title/Abstract])"
              }
            ]'''
        )

        self.assertEqual(len(recovered), 1)
        self.assertIn("short exercise sessions", recovered[0]["search_query"])

    def test_query_builder_removes_unescaped_quotes(self):
        queries = _build_pubmed_queries(
            'short exercise sessions"[Title/Abstract] AND protein synthesis[Title/Abstract]'
        )

        self.assertNotIn('"', queries[0])

    async def test_collect_evidence_discards_articles_not_about_claim(self):
        articles = [
            {"pmid": "training", "title": "Resistance training study"},
            {"pmid": "plaque", "title": "Residual inflammatory risk plaque study"},
        ]
        relevance = [
            {"pmid": "training", "relevance": "RELEVANT", "reason": "Matches claim"},
            {"pmid": "plaque", "relevance": "NOT_RELEVANT", "reason": "Different RIR"},
        ]

        with patch(
            "app.research.fact_checker.search_and_fetch_pubmed",
            new=AsyncMock(return_value=articles),
        ) as search, patch(
            "app.research.fact_checker.analyze_relevance",
            new=AsyncMock(return_value=relevance),
        ):
            evidence = await _collect_evidence(
                [{
                    "claim": "Работа с repetitions in reserve сохраняет технику в силовой тренировке.",
                    "search_query": '"resistance training"[Title/Abstract] AND "repetitions in reserve"[Title/Abstract]',
                }]
            )

        self.assertEqual(evidence[0]["articles"], [articles[0]])
        self.assertEqual(search.await_count, 2)
        self.assertEqual(search.await_args.kwargs["max_results"], 5)

    async def test_collect_evidence_keeps_candidates_if_classifier_rejects_all(self):
        with patch(
            "app.research.fact_checker.search_and_fetch_pubmed",
            new=AsyncMock(return_value=[{"pmid": "plaque"}]),
        ), patch(
            "app.research.fact_checker.analyze_relevance",
            new=AsyncMock(return_value=[{
                "pmid": "plaque",
                "relevance": "NOT_RELEVANT",
                "reason": "RIR refers to inflammatory risk, not repetitions in reserve",
            }]),
        ):
            evidence = await _collect_evidence(
                [{"claim": "RIR в силовой тренировке", "search_query": "resistance training RIR"}]
            )

        self.assertEqual(evidence[0]["articles"], [{"pmid": "plaque"}])
