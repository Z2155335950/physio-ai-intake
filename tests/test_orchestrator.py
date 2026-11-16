from __future__ import annotations

import asyncio
import unittest

from app.agent.safety import DISCLAIMER, REDLINE_REPLY
from app.config import get_settings
from app.domain import ChatRequest
from app.knowledge.local_markdown import MarkdownKnowledgeBase
from app.llm.demo import DemoProvider
from app.llm.base import LLMError
from app.main import create_app
from app.sessions.memory import InMemorySessionStore
from app.agent.orchestrator import AgentOrchestrator


class FailingProvider:
    name = "failing"

    async def generate(
        self,
        *,
        system_prompt,
        messages,
        knowledge,
        customer_memory=None,
    ):
        del system_prompt, messages, knowledge, customer_memory
        raise LLMError("模拟外网模型不可用")


class OrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        settings = get_settings()
        self.orchestrator = AgentOrchestrator(
            settings=settings,
            knowledge_base=MarkdownKnowledgeBase.from_directory(
                settings.knowledge_dir
            ),
            llm=DemoProvider(),
            session_store=InMemorySessionStore(),
        )

    def test_redline_returns_fixed_response(self) -> None:
        response = asyncio.run(
            self.orchestrator.chat(
                ChatRequest(message="帮我看看这个腰椎CT，是不是椎间盘突出")
            )
        )
        self.assertTrue(response.blocked)
        self.assertEqual(response.reply, REDLINE_REPLY)
        self.assertEqual(response.sources, [])

    def test_high_risk_request_does_not_return_a_plan(self) -> None:
        response = asyncio.run(
            self.orchestrator.chat(
                ChatRequest(message="顾客夜间痛醒，还有持续放射麻木怎么办")
            )
        )
        self.assertFalse(response.blocked)
        self.assertEqual(response.risk.level, "high")
        self.assertIn("本次不提供正骨、复位、扳法或具体调理方案", response.reply)
        self.assertIn(DISCLAIMER, response.reply)
        self.assertEqual(response.sources, [])

    def test_demo_mode_returns_sources_and_disclaimer(self) -> None:
        response = asyncio.run(
            self.orchestrator.chat(
                ChatRequest(message="骨盆修复（产康）多少钱几次")
            )
        )
        self.assertFalse(response.blocked)
        self.assertTrue(response.sources)
        self.assertIn("5980", response.reply)
        self.assertIn(DISCLAIMER, response.reply)

    def test_session_keeps_conversation(self) -> None:
        first = asyncio.run(
            self.orchestrator.chat(ChatRequest(message="你好"))
        )
        asyncio.run(
            self.orchestrator.chat(
                ChatRequest(
                    session_id=first.session_id,
                    message="皮肤破皮了能不能贴膏药",
                )
            )
        )
        messages = asyncio.run(
            self.orchestrator.get_session(first.session_id)
        )
        self.assertEqual(len(messages), 4)

    def test_model_failure_falls_back_to_local_knowledge(self) -> None:
        settings = get_settings()
        orchestrator = AgentOrchestrator(
            settings=settings,
            knowledge_base=MarkdownKnowledgeBase.from_directory(
                settings.knowledge_dir,
                policy_file=settings.knowledge_policy_file,
            ),
            llm=FailingProvider(),
            fallback_llm=DemoProvider(),
            session_store=InMemorySessionStore(),
        )
        response = asyncio.run(
            orchestrator.chat(
                ChatRequest(message="骨盆修复多少钱")
            )
        )
        self.assertTrue(response.degraded)
        self.assertIn("本地知识检索摘要", response.warnings[0])
        self.assertTrue(response.sources)
        self.assertIn("5980", response.reply)


class ApiSmokeTests(unittest.TestCase):
    def test_app_exposes_expected_routes(self) -> None:
        app = create_app(get_settings())
        routes = {route.path for route in app.routes}
        self.assertIn("/api/knowledge/search", routes)
        self.assertIn("/api/health", routes)
        self.assertNotIn("/api/chat", routes)
        self.assertNotIn("/api/llm/preview", routes)
        self.assertNotIn("/api/sessions/{session_id}", routes)
        self.assertIn("/service-worker.js", routes)
        self.assertIn("/manifest.webmanifest", routes)


if __name__ == "__main__":
    unittest.main()

