from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.memory.base import CustomerMemoryStore, CustomerNotFoundError
from app.tools.base import (
    ToolContext,
    ToolDefinition,
    ToolExecutionFailed,
    ToolResourceNotFoundError,
)


class CustomerMemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4000)
    recent_limit: int = Field(default=2, ge=1, le=6)
    relevant_limit: int = Field(default=2, ge=0, le=6)


class EmptyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CustomerProfileTool:
    definition = ToolDefinition(
        name="get_customer_profile",
        description="读取当前已选择客户的基础档案和疗程信息",
        input_model=EmptyInput,
        side_effect="read",
        required_scopes=("customer:read",),
        requires_customer_scope=True,
        timeout_seconds=3,
    )

    def __init__(self, memory_store: CustomerMemoryStore) -> None:
        self._memory_store = memory_store

    async def execute(self, arguments: EmptyInput, context: ToolContext) -> Any:
        del arguments
        if not context.customer_id:
            raise ToolExecutionFailed(
                "customer_scope_missing", "工具执行时缺少客户范围"
            )
        try:
            return await self._memory_store.get_customer(context.customer_id)
        except CustomerNotFoundError as exc:
            raise ToolResourceNotFoundError(
                "customer_not_found", str(exc)
            ) from exc


class CustomerMemoryTool:
    definition = ToolDefinition(
        name="get_customer_memory",
        description="读取当前已选择客户的纵向档案和接诊调查记忆",
        input_model=CustomerMemoryInput,
        side_effect="read",
        required_scopes=("customer:read",),
        requires_customer_scope=True,
        timeout_seconds=4,
    )

    def __init__(self, memory_store: CustomerMemoryStore) -> None:
        self._memory_store = memory_store

    async def execute(
        self, arguments: CustomerMemoryInput, context: ToolContext
    ) -> Any:
        if not context.customer_id:
            raise ToolExecutionFailed(
                "customer_scope_missing", "工具执行时缺少客户范围"
            )
        try:
            return await self._memory_store.build_context(
                context.customer_id,
                arguments.query,
                recent_limit=arguments.recent_limit,
                relevant_limit=arguments.relevant_limit,
            )
        except CustomerNotFoundError as exc:
            raise ToolResourceNotFoundError(
                "customer_not_found", str(exc)
            ) from exc

