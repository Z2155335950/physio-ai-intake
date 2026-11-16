from __future__ import annotations

import asyncio
from collections import defaultdict

from app.domain import ChatMessage
from app.sessions.base import SessionScopeError


class InMemorySessionStore:
    """Process-local session store. Replace with a database adapter when needed."""

    def __init__(self, max_messages: int = 40) -> None:
        self._max_messages = max_messages
        self._messages: dict[str, list[ChatMessage]] = defaultdict(list)
        self._customer_bindings: dict[str, str | None] = {}
        self._lock = asyncio.Lock()

    async def get(self, session_id: str) -> list[ChatMessage]:
        async with self._lock:
            return list(self._messages.get(session_id, []))

    async def append(
        self, session_id: str, *messages: ChatMessage
    ) -> list[ChatMessage]:
        async with self._lock:
            conversation = self._messages[session_id]
            conversation.extend(messages)
            if len(conversation) > self._max_messages:
                del conversation[: len(conversation) - self._max_messages]
            return list(conversation)

    async def bind_customer(
        self, session_id: str, customer_id: str | None
    ) -> str | None:
        async with self._lock:
            if session_id not in self._customer_bindings:
                self._customer_bindings[session_id] = customer_id
                return customer_id
            bound_customer_id = self._customer_bindings[session_id]
            if bound_customer_id != customer_id:
                raise SessionScopeError(
                    "当前聊天已绑定其他客户，请新建咨询后再切换客户"
                )
            return bound_customer_id

    async def delete(self, session_id: str) -> bool:
        async with self._lock:
            self._customer_bindings.pop(session_id, None)
            return self._messages.pop(session_id, None) is not None

