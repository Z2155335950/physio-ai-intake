from __future__ import annotations

from app.tools.base import (
    ToolAuthorizationError,
    ToolContext,
    ToolDefinition,
)


class ToolGovernance:
    """Server-side policy decisions. Model output never grants permissions."""

    def authorize(
        self, definition: ToolDefinition, context: ToolContext
    ) -> None:
        if not context.actor_id.strip():
            raise ToolAuthorizationError(
                "actor_missing", "缺少可信操作者身份，拒绝工具调用"
            )

        missing_scopes = sorted(
            set(definition.required_scopes) - set(context.scopes)
        )
        if missing_scopes:
            raise ToolAuthorizationError(
                "scope_denied",
                f"缺少工具权限：{', '.join(missing_scopes)}",
            )

        if definition.requires_customer_scope and not context.customer_id:
            raise ToolAuthorizationError(
                "customer_scope_required",
                "该工具必须在已选择客户的上下文中执行",
            )

        if definition.requires_approval and not context.approval_token:
            raise ToolAuthorizationError(
                "approval_required",
                "该写操作必须经过理疗师显式确认",
            )

        if (
            definition.side_effect == "write"
            and context.risk_level == "high"
            and not definition.high_risk_allowed
        ):
            raise ToolAuthorizationError(
                "high_risk_write_denied",
                "高风险情形下禁止执行写工具",
            )

