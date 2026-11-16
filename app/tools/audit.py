from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(slots=True)
class ToolAuditStart:
    call_id: str
    trace_id: str
    actor_id: str
    customer_id: str | None
    tool_name: str
    side_effect: str
    input_summary: dict


@dataclass(slots=True)
class InMemoryToolAuditStore:
    records: list[dict] = field(default_factory=list)

    async def start(self, record: ToolAuditStart) -> None:
        self.records.append(
            {
                "call_id": record.call_id,
                "trace_id": record.trace_id,
                "actor_id": record.actor_id,
                "customer_id": record.customer_id,
                "tool_name": record.tool_name,
                "side_effect": record.side_effect,
                "input_summary": record.input_summary,
                "status": "running",
            }
        )

    async def finish(
        self,
        call_id: str,
        *,
        status: str,
        duration_ms: int,
        output_summary: dict,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        for record in reversed(self.records):
            if record["call_id"] == call_id:
                record.update(
                    {
                        "status": status,
                        "duration_ms": duration_ms,
                        "output_summary": output_summary,
                        "error_code": error_code,
                        "error_message": error_message,
                    }
                )
                break


class SqliteToolAuditStore:
    """Append-only-style audit log, separate from customer records."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    async def start(self, record: ToolAuditStart) -> None:
        await asyncio.to_thread(self._start_sync, record)

    async def finish(
        self,
        call_id: str,
        *,
        status: str,
        duration_ms: int,
        output_summary: dict,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._finish_sync,
            call_id,
            status,
            duration_ms,
            output_summary,
            error_code,
            error_message,
        )

    def _initialize(self) -> None:
        connection = sqlite3.connect(self._db_path, timeout=10)
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tool_audit (
                    call_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    customer_id TEXT,
                    tool_name TEXT NOT NULL,
                    side_effect TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_summary TEXT NOT NULL,
                    output_summary TEXT NOT NULL DEFAULT '{}',
                    error_code TEXT,
                    error_message TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    duration_ms INTEGER
                );

                CREATE INDEX IF NOT EXISTS idx_tool_audit_trace
                    ON tool_audit(trace_id, started_at);
                CREATE INDEX IF NOT EXISTS idx_tool_audit_customer
                    ON tool_audit(customer_id, started_at);
                """
            )
            connection.commit()
        finally:
            connection.close()

    def _start_sync(self, record: ToolAuditStart) -> None:
        connection = sqlite3.connect(self._db_path, timeout=10)
        try:
            connection.execute(
                """
                INSERT INTO tool_audit (
                    call_id, trace_id, actor_id, customer_id, tool_name,
                    side_effect, status, input_summary, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?)
                """,
                (
                    record.call_id,
                    record.trace_id,
                    record.actor_id,
                    record.customer_id,
                    record.tool_name,
                    record.side_effect,
                    json.dumps(record.input_summary, ensure_ascii=False),
                    self._now(),
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def _finish_sync(
        self,
        call_id: str,
        status: str,
        duration_ms: int,
        output_summary: dict,
        error_code: str | None,
        error_message: str | None,
    ) -> None:
        connection = sqlite3.connect(self._db_path, timeout=10)
        try:
            connection.execute(
                """
                UPDATE tool_audit
                SET status = ?, output_summary = ?, error_code = ?,
                    error_message = ?, finished_at = ?, duration_ms = ?
                WHERE call_id = ?
                """,
                (
                    status,
                    json.dumps(output_summary, ensure_ascii=False),
                    error_code,
                    error_message[:500] if error_message else None,
                    self._now(),
                    duration_ms,
                    call_id,
                ),
            )
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

