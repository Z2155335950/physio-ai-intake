from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.memory.base import VisitCompletionError
from app.memory.models import (
    CustomerCreate,
    CustomerUpdate,
    InvestigationCreate,
)
from app.memory.sqlite_store import SqliteCustomerMemoryStore
from app.tools.audit import InMemoryToolAuditStore
from app.tools.base import ToolAuthorizationError, ToolContext
from app.tools.factory import (
    LOCAL_THERAPIST_SCOPES,
    build_tool_executor,
)


def visit_payload(*, sessions_used: int = 1) -> InvestigationCreate:
    return InvestigationCreate(
        visit_date=date(2026, 11, 11),
        visit_type="复诊",
        chief_complaint="右侧腰部酸胀，较上次缓解",
        current_history="久坐后仍有轻微酸胀，无放射麻木",
        objective_findings="腰方肌区域轻度紧张",
        risk_assessment="适合常规筋膜放松调理",
        care_plan="温和筋膜放松 30 分钟",
        disclosure="已告知正常反应和危险信号",
        sessions_used=sessions_used,
        followup_date=date(2026, 11, 18),
        followup_note="一周后回访腰部舒展情况",
    )


def write_context(customer_id: str, approval_token: str | None = None):
    return ToolContext(
        trace_id="visit-test",
        actor_id="test-therapist",
        scopes=LOCAL_THERAPIST_SCOPES,
        customer_id=customer_id,
        approval_token=approval_token,
    )


class VisitCompletionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SqliteCustomerMemoryStore(
            Path(self.temp_dir.name) / "visits.sqlite3"
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_customer(self, remaining: int = 5):
        return asyncio.run(
            self.store.create_customer(
                CustomerCreate(
                    name="疗程客户",
                    phone="13800000011",
                    selected_course="腰部调理 10 次",
                    remaining_sessions=remaining,
                )
            )
        )

    def test_prepare_and_confirm_are_atomic_and_idempotent(self) -> None:
        customer = self._create_customer(remaining=5)
        proposal = asyncio.run(
            self.store.prepare_visit_completion(
                customer.id, visit_payload(sessions_used=2)
            )
        )
        self.assertEqual(proposal.previous_remaining_sessions, 5)
        self.assertEqual(proposal.proposed_remaining_sessions, 3)

        result = asyncio.run(
            self.store.confirm_visit_completion(
                customer.id, proposal.confirmation_token
            )
        )
        self.assertEqual(result.remaining_sessions, 3)
        self.assertEqual(result.investigation.sessions_used, 2)
        self.assertIsNotNone(result.followup_task)
        self.assertEqual(
            result.followup_task.note, "一周后回访腰部舒展情况"
        )

        detail = asyncio.run(self.store.get_customer_detail(customer.id))
        self.assertEqual(detail.customer.remaining_sessions, 3)
        self.assertEqual(len(detail.investigations), 1)
        self.assertEqual(len(detail.followups), 1)

        with self.assertRaises(VisitCompletionError) as raised:
            asyncio.run(
                self.store.confirm_visit_completion(
                    customer.id, proposal.confirmation_token
                )
            )
        self.assertEqual(raised.exception.code, "confirmation_used")
        persisted = asyncio.run(self.store.get_customer(customer.id))
        self.assertEqual(persisted.remaining_sessions, 3)

    def test_insufficient_sessions_is_rejected_before_confirmation(self) -> None:
        customer = self._create_customer(remaining=1)
        with self.assertRaises(VisitCompletionError) as raised:
            asyncio.run(
                self.store.prepare_visit_completion(
                    customer.id, visit_payload(sessions_used=2)
                )
            )
        self.assertEqual(raised.exception.code, "insufficient_sessions")

    def test_absolute_contraindication_cannot_deduct_sessions(self) -> None:
        customer = self._create_customer(remaining=5)
        payload = visit_payload(sessions_used=1).model_copy(
            update={"risk_assessment": "绝对禁忌，不做正骨复位，建议前往医院就诊"}
        )
        with self.assertRaises(VisitCompletionError) as raised:
            asyncio.run(
                self.store.prepare_visit_completion(customer.id, payload)
            )
        self.assertEqual(
            raised.exception.code, "absolute_contraindication"
        )

    def test_changed_remaining_sessions_invalidates_confirmation(self) -> None:
        customer = self._create_customer(remaining=5)
        proposal = asyncio.run(
            self.store.prepare_visit_completion(
                customer.id, visit_payload(sessions_used=1)
            )
        )
        asyncio.run(
            self.store.update_customer(
                customer.id, CustomerUpdate(remaining_sessions=4)
            )
        )
        with self.assertRaises(VisitCompletionError) as raised:
            asyncio.run(
                self.store.confirm_visit_completion(
                    customer.id, proposal.confirmation_token
                )
            )
        self.assertEqual(raised.exception.code, "stale_confirmation")

    def test_governed_tools_require_approval_and_write_scopes(self) -> None:
        customer = self._create_customer(remaining=5)
        audit = InMemoryToolAuditStore()
        executor = build_tool_executor(
            knowledge_base=knowledge_base(),
            customer_memory=self.store,
            audit_store=audit,
        )
        prepared = asyncio.run(
            executor.execute(
                "prepare_visit_completion",
                visit_payload(sessions_used=1),
                write_context(customer.id),
            )
        )
        token = prepared.data.confirmation_token
        self.assertNotIn(
            visit_payload().chief_complaint, str(audit.records)
        )

        with self.assertRaises(ToolAuthorizationError) as raised:
            asyncio.run(
                executor.execute(
                    "confirm_visit_completion",
                    {"confirmation_token": token},
                    write_context(customer.id),
                )
            )
        self.assertEqual(raised.exception.code, "approval_required")

        confirmed = asyncio.run(
            executor.execute(
                "confirm_visit_completion",
                {"confirmation_token": token},
                write_context(customer.id, approval_token=token),
            )
        )
        self.assertEqual(confirmed.data.remaining_sessions, 4)
        statuses = [record["status"] for record in audit.records]
        self.assertIn("denied", statuses)
        self.assertIn("success", statuses)

    def test_visit_completion_api_round_trip(self) -> None:
        from dataclasses import replace

        from app.config import get_settings
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(
                replace(
                    settings,
                    customer_db_path=Path(temp_dir) / "api-customers.sqlite3",
                    tool_audit_db_path=Path(temp_dir) / "api-audit.sqlite3",
                    staff_access_password="",
                )
            )
            with TestClient(app) as client:
                created = client.post(
                    "/api/customers",
                    json={
                        "name": "接口疗程客户",
                        "selected_course": "腰部调理 10 次",
                        "remaining_sessions": 4,
                    },
                )
                customer_id = created.json()["id"]
                payload = visit_payload(sessions_used=1).model_dump(
                    mode="json"
                )
                prepared = client.post(
                    f"/api/customers/{customer_id}/visits/prepare",
                    json=payload,
                )
                self.assertEqual(prepared.status_code, 200)
                proposal = prepared.json()
                self.assertEqual(proposal["proposed_remaining_sessions"], 3)

                confirmed = client.post(
                    f"/api/customers/{customer_id}/visits/confirm",
                    json={
                        "confirmation_token": proposal["confirmation_token"]
                    },
                )
                self.assertEqual(confirmed.status_code, 200)
                result = confirmed.json()
                self.assertEqual(result["remaining_sessions"], 3)
                self.assertIsNotNone(result["followup_task"])

                insufficient = client.post(
                    f"/api/customers/{customer_id}/visits/prepare",
                    json=visit_payload(sessions_used=4).model_dump(
                        mode="json"
                    ),
                )
                self.assertEqual(insufficient.status_code, 409)
                self.assertIn("剩余次数不足", insufficient.json()["detail"])

                detail = client.get(
                    f"/api/customers/{customer_id}"
                ).json()
                self.assertEqual(
                    detail["customer"]["remaining_sessions"], 3
                )
                self.assertEqual(len(detail["followups"]), 1)


def knowledge_base():
    from app.config import get_settings
    from app.knowledge.local_markdown import MarkdownKnowledgeBase

    settings = get_settings()
    return MarkdownKnowledgeBase.from_directory(
        settings.knowledge_dir,
        policy_file=settings.knowledge_policy_file,
    )


if __name__ == "__main__":
    unittest.main()
