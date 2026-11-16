from __future__ import annotations

from typing import Protocol

from app.domain import ChatMessage


class SessionScopeError(ValueError):
    """Raised when a session attempts to switch customer scope."""


class SessionStore(Protocol):
    async def get(self, session_id: str) -> list[ChatMessage]: ...

    async def append(
        self, session_id: str, *messages: ChatMessage
    ) -> list[ChatMessage]: ...

    async def bind_customer(
        self, session_id: str, customer_id: str | None
    ) -> str | None: ...

    async def delete(self, session_id: str) -> bool: ...

