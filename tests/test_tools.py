from __future__ import annotations

import asyncio
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from app.config import get_settings
from app.knowledge.local_markdown import MarkdownKnowledgeBase
from app.memory.models import CustomerCreate
from app.memory.sqlite_store import SqliteCustomerMemoryStore
from app.tools.audit import InMemoryToolAuditStore, SqliteToolAuditStore
from app.tools.base import (
    ToolAuthorizationError,
    ToolContext,
    ToolDefinition,
    ToolExecutionTimeout,
    ToolInputValidationError,
    ToolNotFoundError,
)
from app.tools.executor import ToolExecutor
from app.tools.factory import DEFAULT_LOCAL_SCOPES, build_tool_executor
from app.tools.governance import ToolGovernance
from app.tools.knowledge import KnowledgeSearchTool
from app.tools.registry import ToolRegistry


class EmptyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SlowTool:
    definition = ToolDefinition(
        name="slow_tool",
        description="测试超时",
        input_model=EmptyInput,
        side_effect="read",
        required_scopes=("test:read",),
        timeout_seconds=0.01,
    )

    async def execute(self, arguments: EmptyInput, context: ToolContext):
        del arguments, context
        await asyncio.sleep(0.1)
        return "late"


class WriteTool:
    definition = ToolDefinition(
        name="write_tool",
        description="测试高风险写操作",
        input_model=EmptyInput,
        side_effect="write",
        required_scopes=("test:write",),
        timeout_seconds=1,
    )

    async def execute(self, arguments: EmptyInput, context: ToolContext):
        del arguments, context
        return "written"


def context(
    *,
    scopes=DEFAULT_LOCAL_SCOPES,
    customer_id: str | None = None,
    risk_level: str = "none",
) -> ToolContext:
    return ToolContext(
        trace_id="test-trace",
        actor_id="test-therapist",
        scopes=frozenset(scopes),
        customer_id=customer_id,
        risk_level=risk_level,
    )


def knowledge_base() -> MarkdownKnowledgeBase:
    settings = get_settings()
    return MarkdownKnowledgeBase.from_directory(settings.knowledge_dir)


class ToolLayerTests(unittest.TestCase):
    def test_registry_rejects_duplicate_tool_names(self) -> None:
        kb = knowledge_base()
        audit = InMemoryToolAuditStore()
        first = build_tool_executor(
            knowledge_base=kb, customer_memory=None, audit_store=audit
        )
        registry = first.registry
        with self.assertRaises(ValueError):
            registry.register(KnowledgeSearchTool(kb))

    def test_read_tool_executes_and_is_audited(self) -> None:
        audit = InMemoryToolAuditStore()
        executor = build_tool_executor(
            knowledge_base=knowledge_base(),
            customer_memory=None,
            audit_store=audit,
        )
        result = asyncio.run(
            executor.execute(
                "search_store_knowledge",
                {"query": "骨盆修复多少钱", "limit": 2},
                context(),
            )
        )
        self.assertEqual(result.tool_name, "search_store_knowledge")
        self.assertTrue(result.data)
        self.assertEqual(audit.records[-1]["status"], "success")
        self.assertIn("sha256", audit.records[-1]["input_summary"]["query"])
        self.assertNotIn("骨盆修复", str(audit.records[-1]["input_summary"]))

    def test_missing_scope_is_denied_and_audited(self) -> None:
        audit = InMemoryToolAuditStore()
        executor = build_tool_executor(
            knowledge_base=knowledge_base(),
            customer_memory=None,
            audit_store=audit,
        )
        with self.assertRaises(ToolAuthorizationError):
            asyncio.run(
                executor.execute(
                    "search_store_knowledge",
                    {"query": "价格"},
                    context(scopes=set()),
                )
            )
        self.assertEqual(audit.records[-1]["status"], "denied")
        self.assertEqual(audit.records[-1]["error_code"], "scope_denied")

    def test_unknown_tool_is_denied_and_audited(self) -> None:
        audit = InMemoryToolAuditStore()
        executor = build_tool_executor(
            knowledge_base=knowledge_base(),
            customer_memory=None,
            audit_store=audit,
        )
        with self.assertRaises(ToolNotFoundError):
            asyncio.run(
                executor.execute(
                    "delete_everything", {}, context(scopes={"admin"})
                )
            )
        self.assertEqual(audit.records[-1]["status"], "denied")
        self.assertEqual(audit.records[-1]["error_code"], "tool_not_found")

    def test_customer_tool_requires_trusted_customer_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SqliteCustomerMemoryStore(
                Path(temp_dir) / "customers.sqlite3"
            )
            audit = InMemoryToolAuditStore()
            executor = build_tool_executor(
                knowledge_base=knowledge_base(),
                customer_memory=store,
                audit_store=audit,
            )
            with self.assertRaises(ToolAuthorizationError):
                asyncio.run(
                    executor.execute(
                        "get_customer_profile", {}, context()
                    )
                )
            self.assertEqual(
                audit.records[-1]["error_code"], "customer_scope_required"
            )

    def test_model_cannot_inject_customer_id_argument(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SqliteCustomerMemoryStore(
                Path(temp_dir) / "customers.sqlite3"
            )
            trusted = asyncio.run(
                store.create_customer(
                    CustomerCreate(name="客户A", phone="13800000001")
                )
            )
            audit = InMemoryToolAuditStore()
            executor = build_tool_executor(
                knowledge_base=knowledge_base(),
                customer_memory=store,
                audit_store=audit,
            )
            with self.assertRaises(ToolInputValidationError):
                asyncio.run(
                    executor.execute(
                        "get_customer_memory",
                        {
                            "query": "历史记录",
                            "customer_id": trusted.id,
                        },
                        context(customer_id=trusted.id),
                    )
                )

    def test_timeout_is_enforced_and_audited(self) -> None:
        audit = InMemoryToolAuditStore()
        registry = ToolRegistry()
        registry.register(SlowTool())
        executor = ToolExecutor(
            registry=registry,
            governance=ToolGovernance(),
            audit_store=audit,
        )
        with self.assertRaises(ToolExecutionTimeout):
            asyncio.run(
                executor.execute(
                    "slow_tool", {}, context(scopes={"test:read"})
                )
            )
        self.assertEqual(audit.records[-1]["status"], "timeout")

    def test_high_risk_write_is_denied(self) -> None:
        audit = InMemoryToolAuditStore()
        registry = ToolRegistry()
        registry.register(WriteTool())
        executor = ToolExecutor(
            registry=registry,
            governance=ToolGovernance(),
            audit_store=audit,
        )
        with self.assertRaises(ToolAuthorizationError):
            asyncio.run(
                executor.execute(
                    "write_tool",
                    {},
                    context(scopes={"test:write"}, risk_level="high"),
                )
            )
        self.assertEqual(
            audit.records[-1]["error_code"], "high_risk_write_denied"
        )

    def test_sqlite_audit_persists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "audit.sqlite3"
            audit = SqliteToolAuditStore(audit_path)
            executor = build_tool_executor(
                knowledge_base=knowledge_base(),
                customer_memory=None,
                audit_store=audit,
            )
            asyncio.run(
                executor.execute(
                    "search_store_knowledge",
                    {"query": "预约规则"},
                    context(),
                )
            )
            connection = sqlite3.connect(audit_path)
            try:
                row = connection.execute(
                    """
                    SELECT status, tool_name, input_summary
                    FROM tool_audit
                    """
                ).fetchone()
            finally:
                connection.close()
            self.assertEqual(row[0], "success")
            self.assertEqual(row[1], "search_store_knowledge")
            self.assertIn("sha256", row[2])

    def test_app_exposes_read_and_governed_write_tools(self) -> None:
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "audit.sqlite3"
            app = create_app(
                replace(
                    settings,
                    customer_db_path=Path(temp_dir) / "customers.sqlite3",
                    tool_audit_db_path=audit_path,
                    llm_provider="demo",
                    staff_access_password="",
                )
            )
            with TestClient(app) as client:
                tools = client.get("/api/tools")
                self.assertEqual(tools.status_code, 200)
                names = {tool["name"] for tool in tools.json()}
                self.assertEqual(
                    names,
                    {
                        "search_store_knowledge",
                        "get_customer_profile",
                        "get_customer_memory",
                        "prepare_visit_completion",
                        "confirm_visit_completion",
                        "schedule_customer_appointment",
                    },
                )
                self.assertEqual(
                    {
                        tool["side_effect"]
                        for tool in tools.json()
                    },
                    {"read", "write"},
                )
                health = client.get("/api/health").json()
                self.assertEqual(health["governed_tool_count"], 6)

                search = client.post(
                    "/api/knowledge/search",
                    json={"query": "骨盆修复多少钱"},
                )
                self.assertEqual(search.status_code, 200)

            connection = sqlite3.connect(audit_path)
            try:
                audit_rows = connection.execute(
                    """
                    SELECT tool_name, status
                    FROM tool_audit
                    WHERE tool_name = 'search_store_knowledge'
                    """
                ).fetchall()
            finally:
                connection.close()
            self.assertTrue(audit_rows)
            self.assertEqual(audit_rows[-1][1], "success")


if __name__ == "__main__":
    unittest.main()
