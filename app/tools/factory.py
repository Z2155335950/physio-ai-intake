from __future__ import annotations

from app.knowledge.base import KnowledgeBase
from app.memory.base import CustomerMemoryStore
from app.tools.appointments import ScheduleAppointmentTool
from app.tools.customer import CustomerMemoryTool, CustomerProfileTool
from app.tools.executor import ToolExecutor
from app.tools.governance import ToolGovernance
from app.tools.knowledge import KnowledgeSearchTool
from app.tools.registry import ToolRegistry
from app.tools.visits import (
    ConfirmVisitCompletionTool,
    PrepareVisitCompletionTool,
)


DEFAULT_LOCAL_SCOPES = frozenset({"knowledge:read", "customer:read"})
LOCAL_THERAPIST_SCOPES = frozenset(
    {"knowledge:read", "customer:read", "customer:write"}
)


def build_tool_executor(
    *,
    knowledge_base: KnowledgeBase,
    customer_memory: CustomerMemoryStore | None,
    audit_store,
) -> ToolExecutor:
    registry = ToolRegistry()
    registry.register(KnowledgeSearchTool(knowledge_base))
    if customer_memory is not None:
        registry.register(CustomerProfileTool(customer_memory))
        registry.register(CustomerMemoryTool(customer_memory))
        registry.register(PrepareVisitCompletionTool(customer_memory))
        registry.register(ConfirmVisitCompletionTool(customer_memory))
        registry.register(ScheduleAppointmentTool(customer_memory))
    return ToolExecutor(
        registry=registry,
        governance=ToolGovernance(),
        audit_store=audit_store,
    )

