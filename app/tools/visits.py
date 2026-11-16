from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.memory.base import CustomerMemoryStore, VisitCompletionError
from app.memory.models import InvestigationCreate
from app.tools.base import (
    ToolAuthorizationError,
    ToolBusinessRuleError,
    ToolContext,
    ToolDefinition,
    ToolExecutionFailed,
)


class ConfirmVisitInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_token: str = Field(min_length=20, max_length=200)


class PrepareVisitCompletionTool:
    definition = ToolDefinition(
        name="prepare_visit_completion",
        description="生成待理疗师确认的接诊完成草稿、次数变更和复诊计划",
        input_model=InvestigationCreate,
        side_effect="write",
        required_scopes=("customer:write",),
        requires_customer_scope=True,
        timeout_seconds=5,
        high_risk_allowed=True,
    )

    def __init__(self, memory_store: CustomerMemoryStore) -> None:
        self._memory_store = memory_store

    async def execute(
        self, arguments: InvestigationCreate, context: ToolContext
    ) -> Any:
        if not context.customer_id:
            raise ToolExecutionFailed(
                "customer_scope_missing", "工具执行时缺少客户范围"
            )
        if context.risk_level == "high" and arguments.sessions_used > 0:
            raise ToolAuthorizationError(
                "high_risk_service_denied",
                "高风险情形只能记录本次情况，不能扣减疗程次数",
            )
        try:
            return await self._memory_store.prepare_visit_completion(
                context.customer_id, arguments
            )
        except VisitCompletionError as exc:
            raise ToolBusinessRuleError(exc.code, str(exc)) from exc


class ConfirmVisitCompletionTool:
    definition = ToolDefinition(
        name="confirm_visit_completion",
        description="在理疗师确认后原子保存接诊、扣减次数并创建复诊任务",
        input_model=ConfirmVisitInput,
        side_effect="write",
        required_scopes=("customer:write",),
        requires_customer_scope=True,
        requires_approval=True,
        timeout_seconds=6,
        high_risk_allowed=True,
    )

    def __init__(self, memory_store: CustomerMemoryStore) -> None:
        self._memory_store = memory_store

    async def execute(
        self, arguments: ConfirmVisitInput, context: ToolContext
    ) -> Any:
        if not context.customer_id:
            raise ToolExecutionFailed(
                "customer_scope_missing", "工具执行时缺少客户范围"
            )
        try:
            return await self._memory_store.confirm_visit_completion(
                context.customer_id, arguments.confirmation_token
            )
        except VisitCompletionError as exc:
            raise ToolBusinessRuleError(exc.code, str(exc)) from exc
