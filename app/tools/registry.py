from __future__ import annotations

import re
from typing import Iterable

from app.tools.base import Tool, ToolDefinition, ToolNotFoundError


_TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        definition = tool.definition
        if not _TOOL_NAME_RE.fullmatch(definition.name):
            raise ValueError(f"非法工具名称: {definition.name}")
        if definition.timeout_seconds <= 0 or definition.timeout_seconds > 30:
            raise ValueError("工具超时时间必须在 0 到 30 秒之间")
        if definition.name in self._tools:
            raise ValueError(f"工具重复注册: {definition.name}")
        self._tools[definition.name] = tool

    def get(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError("tool_not_found", f"未知工具: {name}")
        return tool

    def definitions(self) -> list[ToolDefinition]:
        return [
            self._tools[name].definition for name in sorted(self._tools)
        ]

    def describe(self) -> list[dict]:
        return [
            {
                "name": definition.name,
                "description": definition.description,
                "side_effect": definition.side_effect,
                "required_scopes": list(definition.required_scopes),
                "requires_customer_scope": definition.requires_customer_scope,
                "requires_approval": definition.requires_approval,
                "high_risk_allowed": definition.high_risk_allowed,
                "version": definition.version,
            }
            for definition in self.definitions()
        ]

    def model_schemas(
        self, allowed_names: Iterable[str] | None = None
    ) -> list[dict]:
        allowed = set(allowed_names) if allowed_names is not None else None
        return [
            definition.model_tool_schema()
            for definition in self.definitions()
            if allowed is None or definition.name in allowed
        ]

