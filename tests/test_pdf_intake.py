from __future__ import annotations

import asyncio
import io
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.config import get_settings
from app.domain import ChatMessage
from app.knowledge.base import KnowledgeSearchResult, RetrievedChunk
from app.llm.demo import DemoProvider
from app.memory.models import CustomerCreate, InvestigationCreate
from app.memory.sqlite_store import SqliteCustomerMemoryStore
from app.pdf_intake.extractor import (
    PdfIntakeError,
    extract_pdf_text,
    parse_local_draft,
)
from app.pdf_intake.models import PdfIntakeConfirmRequest
from app.pdf_intake.service import PdfIntakeService
from app.pdf_intake.store import PdfIntakeStore


def text_pdf(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): font}
            )
        }
    )
    stream = DecodedStreamObject()
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(
        f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1")
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class PdfExtractionTests(unittest.TestCase):
    def test_local_parser_extracts_common_intake_fields(self) -> None:
        draft, confidence = parse_local_draft(
            "\n".join(
                [
                    "姓名：张三",
                    "联系电话：13800138000",
                    "年龄：42岁",
                    "性别：男",
                    "现存问题：腰部酸痛",
                    "就诊日期：2026-11-16",
                    "就诊类型：初诊",
                    "主诉：腰部酸痛",
                    "持续时长：两周",
                    "诱发因素：久坐",
                    "既往史：无特殊",
                    "风险评估：无夜间静息痛",
                    "调理方案：温和活动",
                    "复诊日期：2026-11-23",
                    "复诊备注：电话确认时间",
                ]
            )
        )
        self.assertEqual(draft.customer.name, "张三")
        self.assertEqual(draft.customer.phone, "13800138000")
        self.assertEqual(draft.customer.age, "42")
        self.assertEqual(draft.visit.chief_complaint, "腰部酸痛")
        self.assertEqual(draft.visit.trigger, "久坐")
        self.assertEqual(draft.visit.visit_date, date(2026, 11, 16))
        self.assertEqual(draft.visit.followup_date, date(2026, 11, 23))
        self.assertEqual(draft.visit.sessions_used, 0)
        self.assertGreater(confidence["customer.phone"], 0.9)

    def test_pdf_text_layer_is_extracted(self) -> None:
        text, pages = extract_pdf_text(
            text_pdf("Name: Demo; Chief complaint: low back pain")
        )
        self.assertEqual(pages, 1)
        self.assertIn("Name: Demo", text)

    def test_blank_pdf_requires_ocr(self) -> None:
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        output = io.BytesIO()
        writer.write(output)
        with self.assertRaises(PdfIntakeError) as raised:
            extract_pdf_text(output.getvalue())
        self.assertEqual(raised.exception.code, "no_text_layer")


class FakeAIProvider:
    name = "fake-ai"

    def __init__(self) -> None:
        self.messages: list[ChatMessage] = []
        self.system_prompt = ""

    async def generate(self, *, system_prompt, messages, knowledge, customer_memory):
        del knowledge, customer_memory
        self.system_prompt = system_prompt
        self.messages = messages
        return """
        {
          "customer": {
            "name": "", "gender": "", "age": "", "phone": "",
            "occupation": "", "address": "", "health_issues": "腰部酸痛",
            "historical_cases": "", "selected_course": "",
            "remaining_sessions": 0, "notes": ""
          },
          "visit": {
            "visit_date": "2026-11-16", "visit_type": "初诊",
            "chief_complaint": "腰部酸痛", "symptom_duration": "两周",
            "trigger": "久坐", "current_history": "", "medical_history": "",
            "women_special": "", "objective_findings": "",
            "risk_assessment": "无夜间静息痛", "care_plan": "温和活动",
            "disclosure": "", "customer_signature": "",
            "therapist_signature": "", "followup_notes": "",
            "sessions_used": 0, "followup_date": null, "followup_note": ""
          },
          "confidence": {
            "customer.health_issues": 0.92,
            "visit.chief_complaint": 0.94,
            "visit.trigger": 0.88
          }
        }
        """


class KnowledgeAwareAIProvider(FakeAIProvider):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[list[RetrievedChunk]] = []

    async def generate(self, *, system_prompt, messages, knowledge, customer_memory):
        self.calls.append(list(knowledge))
        if "有来源知识助手" in system_prompt:
            self.system_prompt = system_prompt
            self.messages = messages
            return """
            {
              "risk_notice": {"text": "先核对风险资料。", "source_indexes": [1]},
              "communication_script": {"text": "沟通内容仅供参考。", "source_indexes": [2]},
              "customer_handout": {"text": "请按门店说明进行温和活动。", "source_indexes": [3]},
              "draft_completion": {"text": "按门店模板补全记录。", "source_indexes": [4]}
            }
            """
        return await super().generate(
            system_prompt=system_prompt,
            messages=messages,
            knowledge=knowledge,
            customer_memory=customer_memory,
        )


class FakeKnowledgeBase:
    def __init__(self, *, empty: bool = False) -> None:
        self.empty = empty

    @property
    def document_count(self) -> int:
        return 0 if self.empty else 4

    @property
    def chunk_count(self) -> int:
        return 0 if self.empty else 4

    def search(self, query: str, limit: int = 4) -> list[RetrievedChunk]:
        del limit
        if self.empty:
            return []
        if "风险" in query or "禁忌" in query:
            key, source, title = (
                "risk",
                "risk.md",
                "风险筛查规则",
            )
        elif "沟通" in query:
            key, source, title = (
                "communication",
                "communication.md",
                "顾客沟通模板",
            )
        elif "居家养护" in query:
            key, source, title = (
                "handout",
                "handout.md",
                "居家养护说明",
            )
        else:
            key, source, title = (
                "draft",
                "rules.md",
                "接诊记录填写规则",
            )
        return [
            RetrievedChunk(
                chunk_id=key,
                title=title,
                source=source,
                content=f"{title}：这是门店知识库中的测试内容。",
                score=1.0,
                authority_level="A",
                authority_rank=3,
                source_type="store_rule",
                authority_label="门店安全与经营规则",
            )
        ]

    def search_with_diagnostics(
        self, query: str, limit: int = 4
    ) -> KnowledgeSearchResult:
        chunks = self.search(query, limit)
        return KnowledgeSearchResult(
            chunks=chunks,
            conflicts=[],
            candidate_count=len(chunks),
        )


class PdfIntakeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "memory.sqlite3"
        self.memory = SqliteCustomerMemoryStore(self.db_path)
        self.store = PdfIntakeStore(self.db_path)
        self.settings = replace(
            get_settings(),
            llm_provider="demo",
            llm_api_key="",
            llm_base_url="",
            llm_model="",
            llm_send_pii=False,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_preview_and_confirmed_write_are_separate_steps(self) -> None:
        service = PdfIntakeService(
            settings=self.settings,
            llm=DemoProvider(),
            store=self.store,
        )
        source = "\n".join(
            [
                "姓名：李女士",
                "电话：13900139000",
                "年龄：36岁",
                "就诊日期：2026-11-16",
                "主诉：肩颈不适",
                "持续时间：三天",
                "风险提示：无进行性无力",
                "调理方案：放松训练",
                "复诊日期：2026-11-20",
            ]
        )
        with patch(
            "app.pdf_intake.service.extract_pdf_text",
            return_value=(source, 1),
        ):
            preview = asyncio.run(
                service.preview(
                    file_name="intake.pdf",
                    content=text_pdf("mock"),
                    created_by="tester",
                )
            )
        self.assertEqual(preview.extraction_method, "local")
        self.assertEqual(preview.customer.name, "李女士")
        self.assertEqual(preview.visit.chief_complaint, "肩颈不适")

        request = PdfIntakeConfirmRequest(
            draft_id=preview.draft_id,
            customer=CustomerCreate(
                name="李女士",
                phone="13900139000",
                age="36",
                remaining_sessions=5,
            ),
            visit=InvestigationCreate(
                visit_date=date(2026, 11, 16),
                visit_type="初诊",
                chief_complaint="肩颈不适",
                symptom_duration="三天",
                risk_assessment="无进行性无力，建议观察",
                care_plan="放松训练",
                sessions_used=0,
                followup_date=date(2026, 11, 20),
                followup_note="电话确认",
            ),
        )
        result = asyncio.run(
            self.store.confirm(request, confirmed_by="tester")
        )
        self.assertTrue(result.created_customer)
        self.assertTrue(result.followup_id)
        self.assertIsNotNone(result.edit_record_id)
        detail = asyncio.run(
            self.memory.get_customer_detail(result.customer_id)
        )
        self.assertEqual(detail.customer.remaining_sessions, 5)
        self.assertEqual(len(detail.investigations), 1)
        self.assertEqual(len(detail.followups), 1)
        edit_records = asyncio.run(self.store.list_recent_edits(10))
        self.assertEqual(len(edit_records), 1)
        edits_by_path = {
            edit.path: edit for edit in edit_records[0].edits
        }
        self.assertEqual(
            edits_by_path["visit.risk_assessment"].category,
            "medical_judgment",
        )
        self.assertEqual(
            edits_by_path["visit.risk_assessment"].before,
            "无进行性无力",
        )
        self.assertEqual(
            edits_by_path["visit.risk_assessment"].after,
            "无进行性无力，建议观察",
        )
        self.assertEqual(
            edits_by_path["visit.followup_note"].category,
            "expression_style",
        )

        with self.assertRaises(PdfIntakeError) as raised:
            asyncio.run(self.store.confirm(request, confirmed_by="tester"))
        self.assertEqual(raised.exception.code, "already_confirmed")

    def test_ai_preview_redacts_identity_and_uses_ai_clinical_fields(self) -> None:
        provider = FakeAIProvider()
        settings = replace(
            self.settings,
            llm_provider="deepseek",
            llm_api_key="test-key",
            llm_base_url="https://example.invalid/v1",
            llm_model="test-model",
            llm_send_pii=False,
        )
        service = PdfIntakeService(
            settings=settings,
            llm=provider,
            store=self.store,
        )
        source = "\n".join(
            [
                "姓名：王先生",
                "电话：13700137000",
                "地址：佛山禅城区测试路 1 号",
                "就诊日期：2026-11-16",
                "主诉：腰部酸痛",
            ]
        )
        with patch(
            "app.pdf_intake.service.extract_pdf_text",
            return_value=(source, 1),
        ):
            preview = asyncio.run(
                service.preview(
                    file_name="intake.pdf",
                    content=text_pdf("mock"),
                    created_by="tester",
                )
            )
        sent = provider.messages[0].content
        self.assertNotIn("王先生", sent)
        self.assertNotIn("13700137000", sent)
        self.assertNotIn("测试路", sent)
        self.assertEqual(preview.extraction_method, "ai")
        self.assertEqual(preview.customer.name, "王先生")
        self.assertEqual(preview.visit.trigger, "久坐")

    def test_knowledge_assistance_uses_sources_and_refuses_missing_topics(self) -> None:
        provider = KnowledgeAwareAIProvider()
        settings = replace(
            self.settings,
            llm_provider="deepseek",
            llm_api_key="test-key",
            llm_base_url="https://example.invalid/v1",
            llm_model="test-model",
            llm_send_pii=False,
        )
        service = PdfIntakeService(
            settings=settings,
            llm=provider,
            store=self.store,
            knowledge_base=FakeKnowledgeBase(),
        )
        source = "\n".join(
            [
                "姓名：王先生",
                "电话：13700137000",
                "就诊日期：2026-11-16",
                "主诉：腰部酸痛",
            ]
        )
        with patch(
            "app.pdf_intake.service.extract_pdf_text",
            return_value=(source, 1),
        ):
            preview = asyncio.run(
                service.preview(
                    file_name="intake.pdf",
                    content=text_pdf("mock"),
                    created_by="knowledge-therapist",
                )
            )
        self.assertEqual(len(preview.knowledge_assistance), 4)
        self.assertTrue(
            all(item.found for item in preview.knowledge_assistance)
        )
        self.assertTrue(
            all(item.references for item in preview.knowledge_assistance)
        )
        items = {item.topic: item for item in preview.knowledge_assistance}
        self.assertIn("沟通内容", items["communication_script"].text)
        self.assertIn("顾客版", items["customer_handout"].label)
        self.assertEqual(len(provider.calls), 2)
        self.assertNotIn("王先生", provider.messages[0].content)
        self.assertNotIn("13700137000", provider.messages[0].content)

        missing_service = PdfIntakeService(
            settings=self.settings,
            llm=DemoProvider(),
            store=self.store,
            knowledge_base=FakeKnowledgeBase(empty=True),
        )
        with patch(
            "app.pdf_intake.service.extract_pdf_text",
            return_value=(source, 1),
        ):
            missing_preview = asyncio.run(
                missing_service.preview(
                    file_name="missing.pdf",
                    content=text_pdf("mock"),
                    created_by="knowledge-therapist",
                )
            )
        self.assertTrue(
            all(not item.found for item in missing_preview.knowledge_assistance)
        )
        self.assertTrue(
            all(
                item.text == "该内容不在门店知识库范围内，无法提供参考。"
                for item in missing_preview.knowledge_assistance
            )
        )

    def test_existing_customer_and_session_deduction_guard(self) -> None:
        customer = asyncio.run(
            self.memory.create_customer(
                CustomerCreate(
                    name="已有客户",
                    phone="13600136000",
                    remaining_sessions=4,
                )
            )
        )
        service = PdfIntakeService(
            settings=self.settings,
            llm=DemoProvider(),
            store=self.store,
        )
        with patch(
            "app.pdf_intake.service.extract_pdf_text",
            return_value=("主诉：肩部不适", 1),
        ):
            preview = asyncio.run(
                service.preview(
                    file_name="intake.pdf",
                    content=text_pdf("mock"),
                    created_by="tester",
                )
            )
        request = PdfIntakeConfirmRequest(
            draft_id=preview.draft_id,
            customer_id=customer.id,
            visit=InvestigationCreate(
                visit_date=date(2026, 11, 16),
                chief_complaint="肩部不适",
                sessions_used=1,
            ),
        )
        with self.assertRaises(PdfIntakeError) as raised:
            asyncio.run(self.store.confirm(request, confirmed_by="tester"))
        self.assertEqual(raised.exception.code, "sessions_not_supported")

        request.visit.sessions_used = 0
        result = asyncio.run(
            self.store.confirm(request, confirmed_by="tester")
        )
        self.assertFalse(result.created_customer)
        self.assertIsNone(result.edit_record_id)
        detail = asyncio.run(
            self.memory.get_customer_detail(customer.id)
        )
        self.assertEqual(detail.customer.remaining_sessions, 4)
        self.assertEqual(len(detail.investigations), 1)

    def test_repeated_edits_create_approved_preferences_and_are_injected(self) -> None:
        customer = asyncio.run(
            self.memory.create_customer(
                CustomerCreate(name="偏好客户", phone="13500135000")
            )
        )
        service = PdfIntakeService(
            settings=self.settings,
            llm=DemoProvider(),
            store=self.store,
        )
        source = "\n".join(
            [
                "姓名：偏好客户",
                "就诊日期：2026-11-16",
                "就诊类型：初诊",
                "主诉：腰部酸痛",
            ]
        )
        for _ in range(2):
            with patch(
                "app.pdf_intake.service.extract_pdf_text",
                return_value=(source, 1),
            ):
                preview = asyncio.run(
                    service.preview(
                        file_name="intake.pdf",
                        content=text_pdf("mock"),
                        created_by="preference-therapist",
                    )
                )
            request = PdfIntakeConfirmRequest(
                draft_id=preview.draft_id,
                customer_id=customer.id,
                visit=InvestigationCreate(
                    visit_date=date(2026, 11, 16),
                    visit_type="初诊",
                    chief_complaint="腰部酸痛",
                    risk_assessment="需要观察",
                    disclosure="已告知相关注意事项",
                    followup_note="电话确认复诊时间",
                    sessions_used=0,
                ),
            )
            asyncio.run(
                self.store.confirm(
                    request,
                    confirmed_by="preference-therapist",
                )
            )

        overview = asyncio.run(
            self.store.get_preference_overview(
                "preference-therapist", is_admin=False
            )
        )
        candidates = {item.field_path: item for item in overview.candidates}
        self.assertEqual(
            set(candidates),
            {"visit.disclosure", "visit.followup_note"},
        )
        self.assertEqual(
            candidates["visit.followup_note"].category,
            "expression_style",
        )
        self.assertEqual(
            candidates["visit.disclosure"].category,
            "clinic_rule",
        )

        asyncio.run(
            self.store.resolve_preference_candidate(
                candidates["visit.followup_note"].id,
                therapist_id="preference-therapist",
                action="remember_therapist",
                actor="preference-therapist",
            )
        )
        asyncio.run(
            self.store.resolve_preference_candidate(
                candidates["visit.disclosure"].id,
                therapist_id="preference-therapist",
                action="submit_clinic_rule",
                actor="preference-therapist",
            )
        )
        overview = asyncio.run(
            self.store.get_preference_overview(
                "preference-therapist", is_admin=False
            )
        )
        self.assertEqual(len(overview.active_preferences), 1)
        self.assertEqual(len(overview.pending_clinic_rules), 1)

        asyncio.run(
            self.store.review_clinic_preference(
                overview.pending_clinic_rules[0].id,
                action="approve",
                approved_by="manager",
            )
        )
        overview = asyncio.run(
            self.store.get_preference_overview(
                "preference-therapist", is_admin=False
            )
        )
        self.assertEqual(len(overview.active_preferences), 2)

        provider = FakeAIProvider()
        ai_settings = replace(
            self.settings,
            llm_provider="deepseek",
            llm_api_key="test-key",
            llm_base_url="https://example.invalid/v1",
            llm_model="test-model",
            llm_send_pii=False,
        )
        ai_service = PdfIntakeService(
            settings=ai_settings,
            llm=provider,
            store=self.store,
        )
        with patch(
            "app.pdf_intake.service.extract_pdf_text",
            return_value=(source, 1),
        ):
            next_preview = asyncio.run(
                ai_service.preview(
                    file_name="next.pdf",
                    content=text_pdf("mock"),
                    created_by="preference-therapist",
                )
            )
        self.assertEqual(len(next_preview.applied_preferences), 2)
        self.assertIn("门店规则", provider.system_prompt)
        self.assertIn("理疗师偏好", provider.system_prompt)


if __name__ == "__main__":
    unittest.main()
