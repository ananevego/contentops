"""Regression coverage for transient Telegram callback acknowledgement failures."""

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from telegram.error import BadRequest, NetworkError

from app.telegram.handlers import _answer_callback_safely


class CallbackResilienceTests(unittest.IsolatedAsyncioTestCase):
    async def test_network_failure_answering_callback_does_not_abort_handler(self):
        query = SimpleNamespace(
            answer=AsyncMock(side_effect=NetworkError("relay unavailable")),
        )

        await _answer_callback_safely(query)

        query.answer.assert_awaited_once()

    async def test_expired_callback_does_not_abort_handler(self):
        query = SimpleNamespace(
            answer=AsyncMock(side_effect=BadRequest("Query is too old")),
        )

        await _answer_callback_safely(query)

        query.answer.assert_awaited_once()
