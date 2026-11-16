from __future__ import annotations

from app.domain import ChatMessage
from app.knowledge.base import RetrievedChunk
from app.llm.base import LLMError


class UnconfiguredLLMProvider:
    def __init__(self, provider_name: str) -> None:
        self.name = f"{provider_name}-unconfigured"

    async def generate(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        knowledge: list[RetrievedChunk],
        customer_memory: str | None = None,
    ) -> str:
        del system_prompt, messages, knowledge, customer_memory
        raise LLMError("尚未配置 DeepSeek API Key")
