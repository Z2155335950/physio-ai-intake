from __future__ import annotations

import asyncio
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.agent.orchestrator import AgentOrchestrator
from app.config import get_settings
from app.domain import ChatMessage, ChatRequest
from app.knowledge.local_markdown import MarkdownKnowledgeBase
from app.memory.models import (
    CustomerCreate,
    CustomerHandoutUpdate,
    InvestigationCreate,
)
from app.memory.sqlite_store import SqliteCustomerMemoryStore
from app.sessions.base import SessionScopeError
from app.sessions.memory import InMemorySessionStore


class CapturingProvider:
    name = "capturing"

    def __init__(self) -> None:
        self.system_prompts: list[str] = []
        self.memory_contexts: list[str | None] = []

    async def generate(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        knowledge,
        customer_memory: str | None = None,
    ) -> str:
        del messages, knowledge
        self.system_prompts.append(system_prompt)
        self.memory_contexts.append(customer_memory)
        return "已结合当前客户的历史接诊记录整理。"


def customer_payload(name: str, phone: str) -> CustomerCreate:
    return CustomerCreate(name=name, phone=phone, gender="女", age="40")


def investigation_payload(chief_complaint: str, findings: str) -> InvestigationCreate:
    return InvestigationCreate(
        visit_date=date(2026, 11, 11),
        visit_type="初诊",
        chief_complaint=chief_complaint,
        current_history=f"现病史：{chief_complaint}",
        objective_findings=findings,
        risk_assessment="适合常规筋膜放松调理",
        care_plan="仅做温和筋膜放松",
    )


class CustomerMemoryIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "customers.sqlite3"
        self.store = SqliteCustomerMemoryStore(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_customer_profiles_and_records_persist_independently(self) -> None:
        async def scenario():
            customer_a = await self.store.create_customer(
                customer_payload("林女士", "13800000001")
            )
            customer_b = await self.store.create_customer(
                customer_payload("周先生", "13800000002")
            )
            await self.store.add_investigation(
                customer_a.id,
                investigation_payload("右侧腰部酸胀", "腰方肌区域紧张"),
            )
            await self.store.add_investigation(
                customer_b.id,
                investigation_payload("左侧肩颈僵硬", "斜方肌上束紧张"),
            )
            return customer_a, customer_b

        customer_a, customer_b = asyncio.run(scenario())
        reopened = SqliteCustomerMemoryStore(self.db_path)
        detail_a = asyncio.run(reopened.get_customer_detail(customer_a.id))
        detail_b = asyncio.run(reopened.get_customer_detail(customer_b.id))

        self.assertEqual(detail_a.customer.name, "林女士")
        self.assertEqual(len(detail_a.investigations), 1)
        self.assertIn("右侧腰部酸胀", detail_a.investigations[0].chief_complaint)
        self.assertEqual(detail_b.customer.name, "周先生")
        self.assertEqual(len(detail_b.investigations), 1)
        self.assertIn("左侧肩颈僵硬", detail_b.investigations[0].chief_complaint)

    def test_problem_history_and_course_fields_persist(self) -> None:
        async def scenario():
            customer = await self.store.create_customer(
                CustomerCreate(
                    name="疗程测试客户",
                    phone="13800000008",
                    health_issues="长期颈肩僵硬，右侧腰部酸胀",
                    historical_cases="既往腰部扭伤，医院检查记录已由顾客提供",
                    selected_course="骨盆修复 10 次疗程",
                    remaining_sessions=7,
                )
            )
            context = await self.store.build_context(customer.id, "回顾客户疗程")
            return customer, context

        customer, context = asyncio.run(scenario())
        reopened = SqliteCustomerMemoryStore(self.db_path)
        persisted = asyncio.run(reopened.get_customer(customer.id))
        self.assertEqual(persisted.health_issues, "长期颈肩僵硬，右侧腰部酸胀")
        self.assertEqual(
            persisted.historical_cases,
            "既往腰部扭伤，医院检查记录已由顾客提供",
        )
        self.assertEqual(persisted.selected_course, "骨盆修复 10 次疗程")
        self.assertEqual(persisted.remaining_sessions, 7)
        rendered, _ = context.render_for_prompt(include_pii=True)
        self.assertIn("长期颈肩僵硬", rendered)
        self.assertIn("骨盆修复 10 次疗程", rendered)
        self.assertIn("疗程剩余次数：7 次", rendered)

    def test_customer_quick_summary_extracts_risk_and_recent_signals(self) -> None:
        async def scenario():
            customer = await self.store.create_customer(
                CustomerCreate(
                    name="快速卡客户",
                    health_issues="右侧腰部酸胀，久坐加重",
                    historical_cases="既往腰部扭伤，曾到医院检查",
                    selected_course="腰部调理 10 次",
                    remaining_sessions=3,
                )
            )
            await self.store.add_investigation(
                customer.id,
                InvestigationCreate(
                    visit_date=date(2026, 11, 10),
                    visit_type="复诊",
                    chief_complaint="右侧腰部酸胀",
                    current_history="最近夜间痛醒，伴持续右腿放射麻木",
                    objective_findings="右侧腰方肌紧张",
                    risk_assessment="相对禁忌，建议医院评估，仅轻柔放松",
                    followup_notes="上次调理后腰部松一些，但夜间仍有痛醒",
                ),
            )
            return customer

        customer = asyncio.run(scenario())
        detail = asyncio.run(self.store.get_customer_detail(customer.id))
        quick = detail.quick_summary
        self.assertEqual(quick.health_issues, "右侧腰部酸胀，久坐加重")
        self.assertEqual(quick.major_risk_level, "caution")
        self.assertIn("相对禁忌", quick.major_risk)
        self.assertEqual(quick.last_chief_complaint, "右侧腰部酸胀")
        self.assertIn("夜间仍有痛醒", quick.last_followup_feedback)
        self.assertIn("夜间痛/痛醒", quick.recent_danger_signal)
        self.assertIn("持续放射/麻木", quick.recent_danger_signal)
        self.assertEqual(quick.danger_signal_date, date(2026, 11, 10))

    def test_quick_summary_does_not_flag_negated_symptoms(self) -> None:
        async def scenario():
            customer = await self.store.create_customer(
                CustomerCreate(name="无危险信号客户")
            )
            await self.store.add_investigation(
                customer.id,
                InvestigationCreate(
                    visit_date=date(2026, 11, 10),
                    chief_complaint="肩颈僵硬",
                    current_history="无夜间痛，无放射麻木，无肢体无力",
                    risk_assessment="适合常规筋膜放松调理",
                ),
            )
            return customer

        customer = asyncio.run(scenario())
        detail = asyncio.run(self.store.get_customer_detail(customer.id))
        self.assertEqual(detail.quick_summary.recent_danger_signal, "")

    def test_customer_script_and_handout_are_customer_facing(self) -> None:
        async def scenario():
            customer = await self.store.create_customer(
                CustomerCreate(name="沟通测试客户")
            )
            await self.store.add_investigation(
                customer.id,
                InvestigationCreate(
                    visit_date=date(2026, 11, 11),
                    chief_complaint="右侧腰部酸胀",
                    current_history="无夜间痛，无放射麻木",
                    risk_assessment="适合常规筋膜放松调理",
                    care_plan="注意腰部保暖，避免久坐，温和活动",
                ),
            )
            script = await self.store.get_customer_script(customer.id)
            handout = await self.store.get_customer_handout(customer.id)
            return script, handout

        script, handout = asyncio.run(scenario())
        self.assertIn("沟通测试客户您好", script.content)
        self.assertIn("右侧腰部酸胀", script.content)
        self.assertIn("不做疗效承诺", script.content)
        self.assertIn("不能替代医院检查", script.content)
        self.assertIn("注意腰部保暖，避免久坐，温和活动", handout.content)
        self.assertIn("免责：本提示仅作理疗养护参考", handout.content)

    def test_handout_can_be_edited_and_reset(self) -> None:
        customer = asyncio.run(
            self.store.create_customer(CustomerCreate(name="编辑说明客户"))
        )
        customized = asyncio.run(
            self.store.save_customer_handout(
                customer.id,
                CustomerHandoutUpdate(
                    title="编辑后的养护说明",
                    content="这是理疗师修改后的顾客养护文本。",
                ),
            )
        )
        self.assertTrue(customized.is_customized)
        persisted = asyncio.run(
            self.store.get_customer_handout(customer.id)
        )
        self.assertEqual(
            persisted.content, "这是理疗师修改后的顾客养护文本。"
        )
        reset = asyncio.run(
            self.store.reset_customer_handout(customer.id)
        )
        self.assertFalse(reset.is_customized)
        self.assertIn("居家养护说明", reset.title)

    def test_existing_customer_table_is_migrated_in_place(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy.sqlite3"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                CREATE TABLE customers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    gender TEXT NOT NULL DEFAULT '',
                    age TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    occupation TEXT NOT NULL DEFAULT '',
                    address TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                """
                INSERT INTO customers (
                    id, name, created_at, updated_at
                ) VALUES ('legacy-customer', '旧客户', '2026-01-01', '2026-01-01')
                """
            )
            connection.commit()
        finally:
            connection.close()

        migrated = SqliteCustomerMemoryStore(legacy_path)
        customer = asyncio.run(migrated.get_customer("legacy-customer"))
        self.assertEqual(customer.health_issues, "")
        self.assertEqual(customer.historical_cases, "")
        self.assertEqual(customer.selected_course, "")
        self.assertEqual(customer.remaining_sessions, 0)

    def test_memory_context_never_contains_another_customer(self) -> None:
        async def scenario():
            customer_a = await self.store.create_customer(
                customer_payload("林女士", "13800000001")
            )
            customer_b = await self.store.create_customer(
                customer_payload("周先生", "13800000002")
            )
            await self.store.add_investigation(
                customer_a.id,
                investigation_payload(
                    "林女士右侧腰部酸胀",
                    "林女士腰方肌区域紧张",
                ),
            )
            await self.store.add_investigation(
                customer_b.id,
                investigation_payload(
                    "周先生左侧肩颈僵硬",
                    "周先生斜方肌上束紧张",
                ),
            )
            return await self.store.build_context(
                customer_a.id, "右侧腰部酸胀怎么回顾"
            )

        context = asyncio.run(scenario())
        rendered, _ = context.render_for_prompt()
        self.assertIn("林女士", rendered)
        self.assertIn("右侧腰部酸胀", rendered)
        self.assertNotIn("周先生", rendered)
        self.assertNotIn("左侧肩颈僵硬", rendered)

    def test_default_model_memory_is_pseudonymized(self) -> None:
        async def scenario():
            customer = await self.store.create_customer(
                CustomerCreate(
                    name="真实姓名",
                    phone="13912345678",
                    address="某县某路",
                    age="47",
                    occupation="教师",
                    health_issues="腰酸",
                    notes="容易识别客户的备注",
                )
            )
            await self.store.add_investigation(
                customer.id,
                InvestigationCreate(
                    visit_date=date(2026, 11, 11),
                    chief_complaint="腰部酸胀",
                    risk_assessment="适合常规筋膜放松调理",
                ),
            )
            return await self.store.build_context(customer.id, "腰部酸胀")

        rendered, redactions = asyncio.run(scenario()).render_for_prompt()
        self.assertIn("匿名客户编号", rendered)
        self.assertIn("40～49岁", rendered)
        self.assertNotIn("真实姓名", rendered)
        self.assertNotIn("13912345678", rendered)
        self.assertNotIn("某县某路", rendered)
        self.assertNotIn("教师", rendered)
        self.assertNotIn("容易识别客户的备注", rendered)
        self.assertIn("客户姓名", redactions)

    def test_orchestrator_prompt_uses_only_selected_customer_memory(self) -> None:
        async def scenario():
            customer_a = await self.store.create_customer(
                customer_payload("林女士", "13800000001")
            )
            customer_b = await self.store.create_customer(
                customer_payload("周先生", "13800000002")
            )
            await self.store.add_investigation(
                customer_a.id,
                investigation_payload("右侧腰部酸胀", "腰方肌区域紧张"),
            )
            await self.store.add_investigation(
                customer_b.id,
                investigation_payload("左侧肩颈僵硬", "斜方肌上束紧张"),
            )
            return customer_a, customer_b

        customer_a, customer_b = asyncio.run(scenario())
        settings = get_settings()
        provider = CapturingProvider()
        orchestrator = AgentOrchestrator(
            settings=settings,
            knowledge_base=MarkdownKnowledgeBase.from_directory(
                settings.knowledge_dir
            ),
            llm=provider,
            session_store=InMemorySessionStore(),
            customer_memory=self.store,
        )
        response = asyncio.run(
            orchestrator.chat(
                ChatRequest(
                    message="回顾一下这位客户之前的腰部情况",
                    customer_id=customer_a.id,
                )
            )
        )

        self.assertTrue(response.memory_used)
        self.assertEqual(response.customer_id, customer_a.id)
        self.assertTrue(provider.memory_contexts)
        rendered = provider.memory_contexts[-1] or ""
        self.assertIn("右侧腰部酸胀", rendered)
        self.assertNotIn("周先生", rendered)
        self.assertNotIn("左侧肩颈僵硬", rendered)
        self.assertNotIn(customer_b.id, rendered)

    def test_session_cannot_switch_customer_scope(self) -> None:
        async def scenario():
            customer_a = await self.store.create_customer(
                customer_payload("林女士", "13800000001")
            )
            customer_b = await self.store.create_customer(
                customer_payload("周先生", "13800000002")
            )
            settings = get_settings()
            orchestrator = AgentOrchestrator(
                settings=settings,
                knowledge_base=MarkdownKnowledgeBase.from_directory(
                    settings.knowledge_dir
                ),
                llm=CapturingProvider(),
                session_store=InMemorySessionStore(),
                customer_memory=self.store,
            )
            first = await orchestrator.chat(
                ChatRequest(message="你好", customer_id=customer_a.id)
            )
            with self.assertRaises(SessionScopeError):
                await orchestrator.chat(
                    ChatRequest(
                        message="你好",
                        session_id=first.session_id,
                        customer_id=customer_b.id,
                    )
                )

        asyncio.run(scenario())


class CustomerMemoryRouteTests(unittest.TestCase):
    def test_app_exposes_customer_routes(self) -> None:
        settings = get_settings()
        from app.main import create_app

        app = create_app(settings)
        routes = {route.path for route in app.routes}
        self.assertIn("/api/customers", routes)
        self.assertIn("/api/customers/{customer_id}", routes)
        self.assertIn(
            "/api/customers/{customer_id}/investigations",
            routes,
        )

    def test_customer_memory_api_round_trip(self) -> None:
        settings = get_settings()
        from app.main import create_app

        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(
                replace(
                    settings,
                    customer_db_path=Path(temp_dir) / "api-test.sqlite3",
                    tool_audit_db_path=Path(temp_dir) / "api-audit.sqlite3",
                    llm_provider="demo",
                    staff_access_password="",
                )
            )
            with TestClient(app) as client:
                created = client.post(
                    "/api/customers",
                    json={
                        "name": "接口测试客户",
                        "phone": "13800000009",
                        "health_issues": "客户现存问题测试",
                        "historical_cases": "历史病例测试",
                        "selected_course": "全身调理 10 次",
                        "remaining_sessions": 6,
                    },
                )
                self.assertEqual(created.status_code, 201)
                self.assertEqual(created.json()["remaining_sessions"], 6)
                customer_id = created.json()["id"]

                record = client.post(
                    f"/api/customers/{customer_id}/visits/prepare",
                    json={
                        "visit_date": "2026-11-11",
                        "visit_type": "初诊",
                        "chief_complaint": "接口测试腰部记录",
                        "objective_findings": "腰方肌区域紧张",
                    },
                )
                self.assertEqual(record.status_code, 200)
                proposal = record.json()
                confirmed = client.post(
                    f"/api/customers/{customer_id}/visits/confirm",
                    json={
                        "confirmation_token": proposal["confirmation_token"]
                    },
                )
                self.assertEqual(confirmed.status_code, 200)

                detail = client.get(f"/api/customers/{customer_id}")
                self.assertEqual(detail.status_code, 200)
                self.assertEqual(len(detail.json()["investigations"]), 1)
                self.assertEqual(
                    detail.json()["customer"]["health_issues"],
                    "客户现存问题测试",
                )

                script = client.get(
                    f"/api/customers/{customer_id}/customer-script"
                )
                self.assertEqual(script.status_code, 200)
                self.assertIn("接口测试客户您好", script.json()["content"])
                handout = client.get(
                    f"/api/customers/{customer_id}/handout"
                )
                self.assertEqual(handout.status_code, 200)
                self.assertIn("居家养护说明", handout.json()["title"])
                edited = client.put(
                    f"/api/customers/{customer_id}/handout",
                    json={
                        "title": "定制养护说明",
                        "content": "请按门店修改后的内容执行。",
                    },
                )
                self.assertEqual(edited.status_code, 200)
                self.assertTrue(edited.json()["is_customized"])
                self.assertEqual(
                    client.get(
                        f"/api/customers/{customer_id}/handout"
                    ).json()["content"],
                    "请按门店修改后的内容执行。",
                )



if __name__ == "__main__":
    unittest.main()
