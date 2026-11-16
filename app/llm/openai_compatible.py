from __future__ import annotations

import httpx

from app.domain import ChatMessage
from app.knowledge.base import RetrievedChunk
from app.llm.base import LLMError
from app.llm.payload import build_model_system_content


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        provider_name: str = "openai-compatible",
        connect_timeout_seconds: float = 8,
        read_timeout_seconds: float = 30,
        max_output_tokens: int = 800,
    ) -> None:
        self._api_key = api_key
        self.name = provider_name
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = httpx.Timeout(
            read_timeout_seconds,
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=read_timeout_seconds,
            pool=connect_timeout_seconds,
        )
        self._max_output_tokens = max_output_tokens

    async def generate(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        knowledge: list[RetrievedChunk],
        customer_memory: str | None = None,
    ) -> str:
        del customer_memory
        system_content = build_model_system_content(system_prompt, knowledge)
        payload = {
            "model": self._model,
            "temperature": 0.2,
            "max_tokens": self._max_output_tokens,
            "messages": [
                {"role": "system", "content": system_content},
                *[
                    {"role": message.role, "content": message.content}
                    for message in messages
                ],
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise LLMError(
                f"模型服务返回 {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"无法连接模型服务: {exc}") from exc

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError("模型服务返回了无法识别的响应结构") from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMError("模型返回了空内容")
        return content.strip()

