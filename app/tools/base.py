from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel


SideEffect = Literal["read", "write"]


class ToolError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ToolNotFoundError(ToolError):
    pass


class ToolAuthorizationError(ToolError):
    pass


class ToolInputValidationError(ToolError):
    pass


class ToolExecutionTimeout(ToolError):
    pass


class ToolExecutionFailed(ToolError):
    pass


class ToolBusinessRuleError(ToolError):
    pass


class ToolResourceNotFoundError(ToolError):
    pass


@dataclass(frozen=True, slots=True)
class ToolContext:
    trace_id: str
    actor_id: str
    scopes: frozenset[str]
    customer_id: str | None = None
    risk_level: str = "none"
    approval_token: str | None = None


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    side_effect: SideEffect = "read"
    required_scopes: tuple[str, ...] = field(default_factory=tuple)
    requires_customer_scope: bool = False
    requires_approval: bool = False
    high_risk_allowed: bool = False
    timeout_seconds: float = 5.0
    version: str = "1"

    def model_tool_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }


class Tool(Protocol):
    definition: ToolDefinition

    async def execute(self, arguments: BaseModel, context: ToolContext) -> Any: ...


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    call_id: str
    tool_name: str
    data: Any
    duration_ms: int

