from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.generators import content_ideas


class PostGenerationTests(unittest.TestCase):
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
