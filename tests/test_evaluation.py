from __future__ import annotations

import asyncio
import unittest

from app.agent.orchestrator import AgentOrchestrator
from app.config import PROJECT_ROOT, get_settings
from app.evaluation.runner import AgentEvaluator, load_cases
from app.knowledge.local_markdown import MarkdownKnowledgeBase
from app.llm.demo import DemoProvider
from app.sessions.memory import InMemorySessionStore


CASES_FILE = PROJECT_ROOT / "data" / "evaluations" / "core_cases.json"


class EvaluationSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_cases(CASES_FILE)
        settings = get_settings()
        cls.knowledge = MarkdownKnowledgeBase.from_directory(
            settings.knowledge_dir
        )

    def test_core_set_contains_all_eight_categories(self) -> None:
        self.assertEqual(len(self.cases), 19)
        self.assertEqual(len({case.category for case in self.cases}), 8)
        self.assertEqual(len({case.id for case in self.cases}), len(self.cases))

    def test_core_rag_baseline_passes(self) -> None:
        evaluator = AgentEvaluator(
            knowledge_base=self.knowledge,
            top_k=4,
        )
        summary = asyncio.run(
            evaluator.evaluate_all(self.cases, retrieval_only=True)
        )
        self.assertEqual(summary.passed, summary.total)
        self.assertEqual(summary.retrieval_passed, summary.retrieval_total)

    def test_core_end_to_end_baseline_passes_in_demo_mode(self) -> None:
        settings = get_settings()
        orchestrator = AgentOrchestrator(
            settings=settings,
            knowledge_base=self.knowledge,
            llm=DemoProvider(),
            session_store=InMemorySessionStore(),
        )
        evaluator = AgentEvaluator(
            knowledge_base=self.knowledge,
            orchestrator=orchestrator,
            top_k=4,
        )
        summary = asyncio.run(evaluator.evaluate_all(self.cases))
        self.assertEqual(summary.passed, summary.total)
        self.assertEqual(summary.answer_passed, summary.answer_total)


if __name__ == "__main__":
    unittest.main()

