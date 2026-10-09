"""Regression tests for keeping keyword-only PubMed hits out of fact checks."""

import unittest
from unittest.mock import AsyncMock, Mock, patch

from app.research.fact_checker import (
    _build_pubmed_queries,
    _check_evidence,
    _collect_evidence,
    _extract_json,
    _recover_claims_from_malformed_json,
)
from app.research.pubmed import _request_ncbi
from app.research.relevance import analyze_relevance


class FactCheckerRelevanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_pubmed_request_retries_after_rate_limit(self):
        rate_limited = Mock(status_code=429, headers={})
        success = Mock(status_code=200, headers={})
        success.raise_for_status = Mock()
        client = Mock(
            get=AsyncMock(side_effect=[rate_limited, success]),
        )

        with patch(
            "app.research.pubmed._wait_for_ncbi_slot",
            new=AsyncMock(),
        ), patch(
            "app.research.pubmed.asyncio.sleep",
            new=AsyncMock(),
        ) as sleep:
            response = await _request_ncbi(
                client,
                "https://example.test",
                {"query": "test"},
            )

        self.assertIs(response, success)
        self.assertEqual(client.get.await_count, 2)
        sleep.assert_awaited_once_with(1.0)

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
        self.assertIn(
            "creatine AND resistance training AND strength",
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
        self.assertEqual(search.await_count, 3)
        self.assertEqual(search.await_args.kwargs["max_results"], 5)

    async def test_collect_evidence_drops_candidates_if_classifier_rejects_all(self):
        """A keyword-only result must not reach the claim-to-paper matcher."""
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

        self.assertEqual(evidence[0]["articles"], [])

    async def test_relevance_marks_omitted_article_as_not_relevant(self):
        articles = [
            {"pmid": "relevant", "title": "Exercise study", "abstract": ""},
            {"pmid": "omitted", "title": "Other study", "abstract": ""},
        ]
        model_response = '''[
            {"pmid": "relevant", "relevance": "RELEVANT", "reason": "Matches"}
        ]'''

        with patch(
            "app.research.relevance._get_client",
            return_value=Mock(),
        ), patch(
            "app.research.relevance.request_research_completion",
            new=AsyncMock(return_value=model_response),
        ):
            results = await analyze_relevance("Exercise improves strength", articles)

        self.assertEqual(
            results,
            [
                {"pmid": "relevant", "relevance": "RELEVANT", "reason": "Matches"},
                {
                    "pmid": "omitted",
                    "relevance": "NOT_RELEVANT",
                    "reason": "Статья не была классифицирована моделью релевантности.",
                },
            ],
        )

    async def test_fact_checker_rejects_unverifiable_quote_for_supported_claim(self):
        evidence = [{
            "claim": "Креатин повышает максимальную силу у тренированных взрослых.",
            "articles": [{
                "pmid": "42",
                "title": "Creatine and resistance exercise",
                "abstract": "RESULTS: Creatine increased maximal strength in trained adults.",
                "publication_types": ["Randomized Controlled Trial"],
                "publication_date": "2026",
            }],
        }]
        model_response = '''{
            "best_pmid": "42",
            "article_title_ru": "Креатин и силовые упражнения",
            "verdict": "SUPPORTED",
            "reason": "Тезис подтверждён.",
            "evidence_quote": "Creatine improves strength in every athlete"
        }'''

        with patch(
            "app.research.fact_checker.request_research_completion",
            new=AsyncMock(return_value=model_response),
        ):
            result = await _check_evidence(Mock(), evidence)

        self.assertEqual(result[0]["verdict"], "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(result[0]["best_pmid"])
        self.assertEqual(result[0]["evidence_quote"], "")

    async def test_fact_checker_keeps_supported_claim_only_with_exact_evidence_quote(self):
        evidence = [{
            "claim": "Креатин повышает максимальную силу у тренированных взрослых.",
            "articles": [{
                "pmid": "42",
                "title": "Creatine and resistance exercise",
                "abstract": "RESULTS: Creatine increased maximal strength in trained adults.",
                "publication_types": ["Randomized Controlled Trial"],
                "publication_date": "2026",
            }],
        }]
        model_response = '''{
            "best_pmid": "42",
            "article_title_ru": "Креатин и силовые упражнения",
            "verdict": "SUPPORTED",
            "reason": "Тезис подтверждён.",
            "evidence_quote": "Creatine increased maximal strength in trained adults"
        }'''

        with patch(
            "app.research.fact_checker.request_research_completion",
            new=AsyncMock(return_value=model_response),
        ):
            result = await _check_evidence(Mock(), evidence)

        self.assertEqual(result[0]["verdict"], "SUPPORTED")
        self.assertEqual(result[0]["best_pmid"], "42")
        self.assertEqual(
            result[0]["evidence_quote"],
            "Creatine increased maximal strength in trained adults",
        )
