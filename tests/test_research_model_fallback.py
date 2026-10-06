import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.research.model_fallback import request_research_completion


def test_research_model_fallback_uses_next_model_after_empty_response():
    empty_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
    )
    valid_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='[]'))]
    )
    create = AsyncMock(side_effect=[empty_response, valid_response])
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    result = asyncio.run(
        request_research_completion(
            client,
            messages=[{"role": "user", "content": "test"}],
        )
    )

    assert result == "[]"
    assert create.await_count == 2
    assert create.await_args_list[0].kwargs["model"] == "qwen/qwen3-8b"
    assert create.await_args_list[1].kwargs["model"] == "openrouter/free"
