from __future__ import annotations

import asyncio
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import PROJECT_ROOT, get_settings
from app.evaluation.runner import AgentEvaluator, load_cases
from app.knowledge.base import RetrievedChunk
from app.knowledge.conflicts import ConflictDetector
from app.knowledge.local_markdown import MarkdownKnowledgeBase
from app.knowledge.policy import KnowledgePolicy


RAG_CASES_FILE = PROJECT_ROOT / "data" / "evaluations" / "rag_regression_cases.json"
POLICY_FILE = PROJECT_ROOT / "data" / "knowledge_policy.json"
KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "knowledge"


class RagRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.knowledge = MarkdownKnowledgeBase.from_directory(
            KNOWLEDGE_DIR,
            policy_file=POLICY_FILE,
        )

    def test_authority_policy_assigns_expected_levels(self) -> None:
        policy = KnowledgePolicy.load(POLICY_FILE)
        self.assertEqual(
            policy.resolve("正骨风险接诊自查.md").authority_level, "A"
        )
        self.assertEqual(policy.resolve("门店经营类.md").authority_level, "A")
        self.assertEqual(
            policy.resolve("接诊-记录-沟通.md").authority_level, "B"
        )
        self.assertEqual(
            policy.resolve(
                "理疗师学习 · 内部知识笔记（门店专属知识库）.md"
            ).authority_level,
            "C",
        )

    def test_risk_and_policy_queries_are_reranked_to_authoritative_sources(self) -> None:
        risk = self.knowledge.search_with_diagnostics(
            "骨质疏松顾客可以做正骨拉伸吗", limit=4
        )
        self.assertTrue(risk.chunks)
        self.assertEqual(risk.chunks[0].authority_level, "A")
        self.assertIn("正骨风险接诊自查.md", risk.chunks[0].source)

        price = self.knowledge.search_with_diagnostics(
            "骨盆修复多少钱", limit=4
        )
        self.assertTrue(price.chunks)
        self.assertEqual(price.chunks[0].authority_level, "A")
        self.assertIn("门店经营类.md", price.chunks[0].source)

    def test_rag_regression_suite_passes(self) -> None:
        cases = load_cases(RAG_CASES_FILE)
        evaluator = AgentEvaluator(
            knowledge_base=self.knowledge,
            top_k=4,
        )
        summary = asyncio.run(
            evaluator.evaluate_all(cases, retrieval_only=True)
        )
        self.assertEqual(summary.passed, summary.total)
        self.assertEqual(summary.hit_at_k_average, 1.0)
        self.assertEqual(summary.mrr, 1.0)
        self.assertEqual(summary.authority_passed, summary.authority_total)
        self.assertEqual(summary.conflict_passed, summary.conflict_total)

    def test_conflict_prefers_more_restrictive_authoritative_source(self) -> None:
        chunks = [
            RetrievedChunk(
                chunk_id="a",
                title="安全规则",
                source="安全规则.md",
                content="骨质疏松顾客禁止正骨复位。",
                score=1,
                authority_level="A",
                authority_rank=100,
                source_type="safety_policy",
            ),
            RetrievedChunk(
                chunk_id="c",
                title="培训记录",
                source="培训记录.md",
                content="这种情况可以正骨调理。",
                score=0.9,
                authority_level="C",
                authority_rank=55,
                source_type="internal_training",
            ),
        ]
        conflicts = ConflictDetector().detect(chunks, "这种情况能不能正骨")
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].preferred_source, "安全规则.md")
        self.assertEqual(conflicts[0].preferred_authority, "A")
        self.assertIn("限制更强", conflicts[0].resolution)

    def test_conflict_detector_ignores_unrelated_topic(self) -> None:
        chunks = [
            RetrievedChunk(
                chunk_id="a",
                title="安全规则",
                source="a.md",
                content="禁止正骨复位。",
                score=1,
                authority_level="A",
                authority_rank=100,
            ),
            RetrievedChunk(
                chunk_id="b",
                title="培训记录",
                source="b.md",
                content="可以正骨调理。",
                score=1,
                authority_level="C",
                authority_rank=50,
            ),
        ]
        self.assertEqual(
            ConflictDetector().detect(chunks, "门店预约规则是什么"),
            [],
        )

    def test_knowledge_search_surfaces_conflict_metadata(self) -> None:
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(
                replace(
                    settings,
                    customer_db_path=Path(temp_dir) / "customers.sqlite3",
                    tool_audit_db_path=Path(temp_dir) / "audit.sqlite3",
                    staff_access_password="",
                )
            )
            with TestClient(app) as client:
                response = client.post(
                    "/api/knowledge/search",
                    json={
                        "query": "顾客骨质疏松，非要正骨，我怎么委婉拒绝"
                    },
                )
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["knowledge_conflicts"])
                self.assertEqual(payload["sources"][0]["authority_level"], "B")


if __name__ == "__main__":
    unittest.main()
