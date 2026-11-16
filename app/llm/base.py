from __future__ import annotations

from typing import Protocol

from app.domain import ChatMessage
from app.knowledge.base import RetrievedChunk


class LLMError(RuntimeError):
    """Raised when a model request cannot produce a usable response."""


class LLMProvider(Protocol):
    name: str

    async def generate(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        knowledge: list[RetrievedChunk],
        customer_memory: str | None = None,
    ) -> str: ...

