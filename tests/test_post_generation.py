from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.generators import content_ideas


class PostGenerationTests(unittest.TestCase):
    def test_idea_generation_uses_fallback_after_empty_response(self):
        empty_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
        )
        valid_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Готовая идея"))]
        )
        create = Mock(
            side_effect=[empty_response, valid_response],
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        item = SimpleNamespace(
            transcript=None,
            author="Автор",
            text="Текст",
            views=1,
            likes=1,
            comments=1,
            shares=1,
            trend_score=1,
            url="https://example.test",
        )

        with patch.object(
            content_ideas,
            "get_openrouter_client",
            return_value=client,
        ):
            result = content_ideas.generate_content_idea(item)

        self.assertEqual(result, "Готовая идея")
        self.assertEqual(create.call_count, 2)
        self.assertEqual(create.call_args_list[1].kwargs["model"], "openrouter/free")

    def test_incomplete_model_responses_raise_instead_of_returning_idea(self):
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Короткий ответ."),
                    finish_reason="stop",
                )
            ]
        )

        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=lambda **_kwargs: response)
            )
        )

        with patch.object(
            content_ideas,
            "get_openrouter_client",
            return_value=client,
        ):
            with self.assertRaises(content_ideas.PostGenerationError):
                content_ideas.generate_telegram_post("Исходная идея")

    def test_complete_post_is_accepted(self):
        post = "А" * 1_200 + "."

        self.assertTrue(content_ideas.is_complete_post(post, "stop"))
