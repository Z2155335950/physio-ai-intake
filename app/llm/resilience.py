from __future__ import annotations

import asyncio
import time

from app.domain import ChatMessage
from app.knowledge.base import RetrievedChunk
from app.llm.base import LLMError, LLMProvider


class CircuitBreakerLLMProvider:
    """Short-circuit repeated online failures while the local fallback remains available."""

    def __init__(
        self,
        primary: LLMProvider,
        *,
        failure_threshold: int = 3,
        cooldown_seconds: int = 300,
    ) -> None:
        self._primary = primary
        self.name = primary.name
        self._failure_threshold = max(1, failure_threshold)
        self._cooldown_seconds = max(1, cooldown_seconds)
        self._failures = 0
        self._opened_until = 0.0
        self._lock = asyncio.Lock()

    async def generate(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        knowledge: list[RetrievedChunk],
        customer_memory: str | None = None,
    ) -> str:
        now = time.monotonic()
        async with self._lock:
            if self._opened_until > now:
                remaining = int(self._opened_until - now)
                raise LLMError(
                    f"在线模型连续失败，熔断中，约 {remaining} 秒后重试"
                )
            if self._opened_until and self._opened_until <= now:
                self._opened_until = 0.0
                self._failures = 0

        try:
            reply = await self._primary.generate(
                system_prompt=system_prompt,
                messages=messages,
                knowledge=knowledge,
                customer_memory=customer_memory,
            )
        except LLMError:
            async with self._lock:
                self._failures += 1
                if self._failures >= self._failure_threshold:
                    self._opened_until = (
                        time.monotonic() + self._cooldown_seconds
                    )
            raise
        else:
            async with self._lock:
                self._failures = 0
                self._opened_until = 0.0
            return reply

    def status(self) -> dict:
        remaining = max(0, int(self._opened_until - time.monotonic()))
        return {
            "provider": self._primary.name,
            "circuit_open": remaining > 0,
            "retry_after_seconds": remaining,
            "consecutive_failures": self._failures,
        }
