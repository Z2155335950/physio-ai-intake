from __future__ import annotations

import unittest
from pathlib import Path

from app.knowledge.local_markdown import MarkdownKnowledgeBase


KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"


class KnowledgeBaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.knowledge = MarkdownKnowledgeBase.from_directory(KNOWLEDGE_DIR)

    def test_loads_business_knowledge(self) -> None:
        self.assertEqual(self.knowledge.document_count, 5)
        self.assertGreater(self.knowledge.chunk_count, 20)

    def test_price_lookup_hits_store_pricing(self) -> None:
        results = self.knowledge.search("骨盆修复（产康）多少钱几次", limit=4)
        self.assertTrue(results)
        self.assertTrue(
            any("门店经营类.md" in result.source for result in results)
        )
        self.assertTrue(any("5980" in result.content for result in results))

    def test_single_session_price_lookup(self) -> None:
        results = self.knowledge.search("全身痛症单次体验多少钱", limit=4)
        self.assertTrue(results)
        self.assertTrue(any("200" in result.content for result in results))

    def test_blood_pressure_lookup_hits_baseline_guidance(self) -> None:
        results = self.knowledge.search(
            "血压165/102的顾客，可以做颈椎正骨吗", limit=4
        )
        self.assertTrue(results)
        self.assertTrue(
            any(
                "160" in result.content or "禁止正骨" in result.content
                for result in results
            )
        )

    def test_test_documents_are_not_indexed(self) -> None:
        self.assertFalse(
            any(
                "测试用文档" in result.source
                for result in self.knowledge.search("测试用例和系统提示词", limit=10)
            )
        )


if __name__ == "__main__":
    unittest.main()

