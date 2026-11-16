from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from typing import Any

from pydantic import BaseModel, ValidationError

from app.knowledge.base import KnowledgeSearchResult
from app.tools.audit import ToolAuditStart
from app.tools.base import (
    ToolContext,
    ToolError,
    ToolExecutionFailed,
    ToolExecutionResult,
    ToolExecutionTimeout,
    ToolInputValidationError,
    ToolNotFoundError,
)
from app.tools.governance import ToolGovernance
from app.tools.registry import ToolRegistry


def summarize_input(arguments: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key, value in arguments.items():
        if isinstance(value, str):
            summary[key] = {
                "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
                "length": len(value),
            }
        elif isinstance(value, (int, float, bool)) or value is None:
            summary[key] = value
        else:
            summary[key] = {"type": type(value).__name__}
    return summary


def summarize_output(data: Any) -> dict[str, Any]:
    if isinstance(data, KnowledgeSearchResult):
        return {
            "type": "KnowledgeSearchResult",
            "chunk_count": len(data.chunks),
            "candidate_count": data.candidate_count,
            "sources": list(
                dict.fromkeys(item.source for item in data.chunks)
            ),
            "conflict_count": len(data.conflicts),
            "conflict_topics": [item.topic for item in data.conflicts],
        }
    if isinstance(data, list):
        return {"type": "list", "count": len(data)}
    if isinstance(data, BaseModel):
        return {"type": data.__class__.__name__}
    if isinstance(data, dict):
        return {"type": "dict", "keys": sorted(str(key) for key in data)}
    return {"type": type(data).__name__}


class ToolExecutor:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        governance: ToolGovernance,
        audit_store,
    ) -> None:
        self.registry = registry
        self._governance = governance
        self._audit_store = audit_store

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any] | BaseModel | None,
        context: ToolContext,
    ) -> ToolExecutionResult:
        call_id = str(uuid.uuid4())
        started = time.perf_counter()
        raw_arguments = (
            arguments.model_dump()
            if isinstance(arguments, BaseModel)
            else dict(arguments or {})
        )

        try:
            tool = self.registry.get(tool_name)
            definition = tool.definition
        except ToolNotFoundError as exc:
            await self._record_denial(
                call_id=call_id,
                context=context,
                tool_name=tool_name,
                side_effect="unknown",
                arguments=raw_arguments,
                exc=exc,
            )
            raise

        await self._audit_store.start(
            ToolAuditStart(
                call_id=call_id,
                trace_id=context.trace_id,
                actor_id=context.actor_id,
                customer_id=context.customer_id,
                tool_name=tool_name,
                side_effect=definition.side_effect,
                input_summary=summarize_input(raw_arguments),
            )
        )

        try:
            self._governance.authorize(definition, context)
            try:
                validated = definition.input_model.model_validate(raw_arguments)
            except ValidationError as exc:
                raise ToolInputValidationError(
                    "invalid_arguments", f"工具参数校验失败: {exc}"
                ) from exc

            data = await asyncio.wait_for(
                tool.execute(validated, context),
                timeout=definition.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            error = ToolExecutionTimeout(
                "timeout", f"工具执行超过 {definition.timeout_seconds:g} 秒"
            )
            await self._finish(call_id, started, "timeout", {}, error)
            raise error from exc
        except ToolError as exc:
            denied_codes = {
                "scope_denied",
                "customer_scope_required",
                "actor_missing",
                "high_risk_write_denied",
                "approval_required",
                "high_risk_service_denied",
            }
            await self._finish(
                call_id,
                started,
                "denied" if exc.code in denied_codes else "failed",
                {},
                exc,
            )
            raise
        except Exception as exc:
            error = ToolExecutionFailed("tool_failed", "工具执行失败")
            await self._finish(call_id, started, "failed", {}, error, exc)
            raise error from exc

        duration_ms = int((time.perf_counter() - started) * 1000)
        await self._audit_store.finish(
            call_id,
            status="success",
            duration_ms=duration_ms,
            output_summary=summarize_output(data),
        )
        return ToolExecutionResult(
            call_id=call_id,
            tool_name=tool_name,
            data=data,
            duration_ms=duration_ms,
        )

    async def _record_denial(
        self,
        *,
        call_id: str,
        context: ToolContext,
        tool_name: str,
        side_effect: str,
        arguments: dict[str, Any],
        exc: ToolError,
    ) -> None:
        await self._audit_store.start(
            ToolAuditStart(
                call_id=call_id,
                trace_id=context.trace_id,
                actor_id=context.actor_id,
                customer_id=context.customer_id,
                tool_name=tool_name,
                side_effect=side_effect,
                input_summary=summarize_input(arguments),
            )
        )
        await self._audit_store.finish(
            call_id,
            status="denied",
            duration_ms=0,
            output_summary={},
            error_code=exc.code,
            error_message=str(exc),
        )

    async def _finish(
        self,
        call_id: str,
        started: float,
        status: str,
        output_summary: dict,
        error: ToolError,
        original_error: Exception | None = None,
    ) -> None:
        await self._audit_store.finish(
            call_id,
            status=status,
            duration_ms=int((time.perf_counter() - started) * 1000),
            output_summary=output_summary,
            error_code=error.code,
            error_message=(
                str(original_error) if original_error is not None else str(error)
            ),
        )

