from __future__ import annotations

from app.domain import ChatMessage
from app.knowledge.base import RetrievedChunk


class DemoProvider:
    """Deterministic local provider for development and offline evaluation."""

    name = "demo"

    async def generate(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        knowledge: list[RetrievedChunk],
        customer_memory: str | None = None,
    ) -> str:
        del system_prompt, messages
        if not knowledge and not customer_memory:
            return "该内容不在门店知识库范围内，无法提供参考。"

        sections: list[str] = ["当前为本地演示模式。"]
        if customer_memory:
            sections.append(
                "**当前客户记忆（仅展示已选择客户的隔离记录）**\n"
                f"{customer_memory}"
            )
        for index, chunk in enumerate(knowledge[:3], start=1):
            excerpt = chunk.content.strip()
            if len(excerpt) > 700:
                excerpt = f"{excerpt[:700].rstrip()}…"
            sections.append(
                f"**参考 {index}：{chunk.title}**"
                f"（{chunk.authority_label}，{chunk.authority_level} 级）\n"
                f"{excerpt}\n"
                f"来源：`{chunk.source}`"
            )
        return "\n\n".join(sections)

