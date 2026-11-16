from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.memory.base import VisitCompletionError
from app.memory.models import (
    CustomerCreate,
    FollowupStatusUpdate,
    InvestigationCreate,
)
from app.memory.sqlite_store import SqliteCustomerMemoryStore


class FollowupTaskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SqliteCustomerMemoryStore(
            Path(self.temp_dir.name) / "followups.sqlite3"
        )
        self.customer = asyncio.run(
            self.store.create_customer(
                CustomerCreate(name="复诊客户", phone="13800007777")
            )
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_followup(self, due_date: date):
        payload = InvestigationCreate(
            visit_date=date(2026, 11, 14),
            chief_complaint="腰部酸胀",
            risk_assessment="适合常规筋膜放松调理",
            sessions_used=0,
            followup_date=due_date,
            followup_note="请按时复诊",
        )
        proposal = asyncio.run(
            self.store.prepare_visit_completion(self.customer.id, payload)
        )
        result = asyncio.run(
            self.store.confirm_visit_completion(
                self.customer.id, proposal.confirmation_token
            )
        )
        return result.followup_task

    def test_completed_visit_and_phone_followup(self) -> None:
        task = self._create_followup(date(2026, 11, 15))
        completed = asyncio.run(
            self.store.update_followup_status(
                self.customer.id,
                task.id,
                FollowupStatusUpdate(
                    status="completed",
                    completion_type="visited",
                    resolution_note="已完成本次复诊",
                ),
            )
        )
        self.assertEqual(completed.status, "completed")
        self.assertEqual(completed.completion_type, "visited")
        self.assertIsNotNone(completed.completed_at)
        dashboard = asyncio.run(
            self.store.get_today_dashboard(date(2026, 11, 15))
        )
        self.assertEqual(dashboard.followup_count, 0)

        with self.assertRaises(VisitCompletionError):
            asyncio.run(
                self.store.update_followup_status(
                    self.customer.id,
                    task.id,
                    FollowupStatusUpdate(
                        status="cancelled",
                        resolution_note="重复操作",
                    ),
                )
            )

    def test_phone_followup_completion(self) -> None:
        task = self._create_followup(date(2026, 11, 16))
        completed = asyncio.run(
            self.store.update_followup_status(
                self.customer.id,
                task.id,
                FollowupStatusUpdate(
                    status="completed",
                    completion_type="phone_followup",
                ),
            )
        )
        self.assertEqual(completed.completion_type, "phone_followup")

    def test_deferred_followup_can_be_restored(self) -> None:
        task = self._create_followup(date(2026, 11, 17))
        deferred = asyncio.run(
            self.store.update_followup_status(
                self.customer.id,
                task.id,
                FollowupStatusUpdate(
                    status="deferred",
                    resolution_note="顾客近期外出",
                ),
            )
        )
        self.assertEqual(deferred.status, "deferred")
        restored = asyncio.run(
            self.store.update_followup_status(
                self.customer.id,
                task.id,
                FollowupStatusUpdate(status="pending"),
            )
        )
        self.assertEqual(restored.status, "pending")
        self.assertIsNone(restored.completed_at)

    def test_cancelled_followup_is_final(self) -> None:
        task = self._create_followup(date(2026, 11, 18))
        cancelled = asyncio.run(
            self.store.update_followup_status(
                self.customer.id,
                task.id,
                FollowupStatusUpdate(
                    status="cancelled",
                    resolution_note="顾客取消后续安排",
                ),
            )
        )
        self.assertEqual(cancelled.status, "cancelled")
        with self.assertRaises(VisitCompletionError):
            asyncio.run(
                self.store.update_followup_status(
                    self.customer.id,
                    task.id,
                    FollowupStatusUpdate(status="pending"),
                )
            )


if __name__ == "__main__":
    unittest.main()
