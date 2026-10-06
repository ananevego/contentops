"""Resilient OpenRouter completions for research-stage JSON tasks."""

import asyncio

from openai import AsyncOpenAI


RESEARCH_MODELS = [
    "qwen/qwen3-8b",
    "openrouter/free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "thinkingmachines/inkling:free",
    "inclusionai/ling-3.0-flash-sante:free",
    "nex-agi/nex-n2.5-mini:free",
]


async def request_research_completion(
    client: AsyncOpenAI,
    messages: list[dict],
    temperature: float = 0,
) -> str:
    """Returns the first non-empty completion from the configured fallbacks."""
    errors = []

    for model in RESEARCH_MODELS:
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            content = response.choices[0].message.content
            if isinstance(content, str) and content.strip():
                return content
            errors.append(f"{model}: empty response")
        except Exception as error:
            errors.append(f"{model}: {type(error).__name__}")

        # Avoid sending an immediate burst when an upstream free model is busy.
        await asyncio.sleep(0.5)

    raise RuntimeError(
        "Research models unavailable after fallbacks: "
        + "; ".join(errors)
    )
