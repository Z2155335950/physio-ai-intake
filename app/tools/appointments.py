from __future__ import annotations

from typing import Any

from app.memory.base import CustomerMemoryStore, CustomerNotFoundError
from app.memory.models import AppointmentCreate
from app.tools.base import (
    ToolContext,
    ToolDefinition,
    ToolExecutionFailed,
    ToolResourceNotFoundError,
)


class ScheduleAppointmentTool:
    definition = ToolDefinition(
        name="schedule_customer_appointment",
        description="为当前客户创建预约，并进入今日工作台",
        input_model=AppointmentCreate,
        side_effect="write",
        required_scopes=("customer:write",),
        requires_customer_scope=True,
        timeout_seconds=4,
        high_risk_allowed=True,
    )

    def __init__(self, memory_store: CustomerMemoryStore) -> None:
        self._memory_store = memory_store

    async def execute(
        self, arguments: AppointmentCreate, context: ToolContext
    ) -> Any:
        if not context.customer_id:
            raise ToolExecutionFailed(
                "customer_scope_missing", "工具执行时缺少客户范围"
            )
        try:
            return await self._memory_store.create_appointment(
                context.customer_id, arguments
            )
        except CustomerNotFoundError as exc:
            raise ToolResourceNotFoundError(
                "customer_not_found", str(exc)
            ) from exc
