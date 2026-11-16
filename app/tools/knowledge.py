from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.knowledge.base import KnowledgeBase
from app.tools.base import ToolContext, ToolDefinition


class KnowledgeSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=4, ge=1, le=10)


class KnowledgeSearchTool:
    definition = ToolDefinition(
        name="search_store_knowledge",
        description="检索门店公共知识库，包括解剖、禁忌、价格、规则和沟通模板",
        input_model=KnowledgeSearchInput,
        side_effect="read",
        required_scopes=("knowledge:read",),
        timeout_seconds=4,
    )

    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self._knowledge_base = knowledge_base

    async def execute(
        self, arguments: KnowledgeSearchInput, context: ToolContext
    ) -> Any:
        del context
        return self._knowledge_base.search_with_diagnostics(
            arguments.query.strip(), limit=arguments.limit
        )

