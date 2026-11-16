from __future__ import annotations

import asyncio
import unittest
from dataclasses import replace

from app.config import get_settings
from app.domain import ChatMessage
from app.llm.base import LLMError
from app.llm.resilience import CircuitBreakerLLMProvider
from app.llm.unconfigured import UnconfiguredLLMProvider
from app.main import create_llm


class AlwaysFailProvider:
    name = "always-fail"

    async def generate(self, **kwargs):
        del kwargs
        raise LLMError("network unavailable")


class RecoveringProvider:
    name = "recovering"

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, **kwargs):
        del kwargs
        self.calls += 1
        if self.calls == 1:
            raise LLMError("temporary failure")
        return "online response"


class CircuitBreakerTests(unittest.TestCase):
    def test_opens_after_threshold_and_short_circuits(self) -> None:
        provider = CircuitBreakerLLMProvider(
            AlwaysFailProvider(),
            failure_threshold=2,
            cooldown_seconds=60,
        )
        kwargs = {
            "system_prompt": "system",
            "messages": [ChatMessage(role="user", content="hello")],
            "knowledge": [],
        }
        for _ in range(2):
            with self.assertRaises(LLMError):
                asyncio.run(provider.generate(**kwargs))
        status = provider.status()
        self.assertTrue(status["circuit_open"])
        self.assertEqual(status["consecutive_failures"], 2)
        with self.assertRaises(LLMError) as raised:
            asyncio.run(provider.generate(**kwargs))
        self.assertIn("熔断", str(raised.exception))

    def test_success_resets_failure_count(self) -> None:
        primary = RecoveringProvider()
        provider = CircuitBreakerLLMProvider(
            primary,
            failure_threshold=2,
            cooldown_seconds=60,
        )
        kwargs = {
            "system_prompt": "system",
            "messages": [ChatMessage(role="user", content="hello")],
            "knowledge": [],
        }
        with self.assertRaises(LLMError):
            asyncio.run(provider.generate(**kwargs))
        reply = asyncio.run(provider.generate(**kwargs))
        self.assertEqual(reply, "online response")
        self.assertEqual(provider.status()["consecutive_failures"], 0)

    def test_deepseek_without_key_uses_unconfigured_provider(self) -> None:
        settings = replace(
            get_settings(),
            llm_provider="deepseek",
            llm_api_key="",
            llm_base_url="https://api.deepseek.com/v1",
            llm_model="deepseek-chat",
        )
        provider = create_llm(settings)
        self.assertIsInstance(provider, UnconfiguredLLMProvider)

    def test_configured_deepseek_is_wrapped_with_circuit_breaker(self) -> None:
        settings = replace(
            get_settings(),
            llm_provider="deepseek",
            llm_api_key="test-key",
            llm_base_url="https://api.deepseek.com/v1",
            llm_model="deepseek-chat",
        )
        provider = create_llm(settings)
        self.assertIsInstance(provider, CircuitBreakerLLMProvider)
        self.assertEqual(provider.name, "deepseek")


if __name__ == "__main__":
    unittest.main()
