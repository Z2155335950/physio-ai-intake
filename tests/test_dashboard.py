from __future__ import annotations

import asyncio
import tempfile
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import get_settings
from app.memory.models import (
    AppointmentCreate,
    CustomerCreate,
    InvestigationCreate,
)
from app.memory.sqlite_store import SqliteCustomerMemoryStore


def visit(
    *,
    visit_date: date,
    complaint: str,
    risk: str,
    sessions_used: int = 0,
    followup_date: date | None = None,
) -> InvestigationCreate:
    return InvestigationCreate(
        visit_date=visit_date,
        visit_type="复诊",
        chief_complaint=complaint,
        risk_assessment=risk,
        care_plan="温和筋膜放松",
        followup_notes="上次反馈稳定",
        sessions_used=sessions_used,
        followup_date=followup_date,
        followup_note="请安排复诊" if followup_date else "",
    )


class TodayDashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SqliteCustomerMemoryStore(
            Path(self.temp_dir.name) / "dashboard.sqlite3"
        )
        self.today = date(2026, 11, 11)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _customer(
        self,
        name: str,
        *,
        remaining: int = 5,
        course: str = "",
    ):
        return asyncio.run(
            self.store.create_customer(
                CustomerCreate(
                    name=name,
                    phone=f"1380000{remaining:04d}",
                    selected_course=course,
                    remaining_sessions=remaining,
                )
            )
        )

    def test_dashboard_aggregates_all_workbench_sections(self) -> None:
        appointment_customer = self._customer(
            "今日预约客户", remaining=1, course="腰部调理 10 次"
        )
        asyncio.run(
            self.store.create_appointment(
                appointment_customer.id,
                AppointmentCreate(
                    scheduled_at=datetime(2026, 11, 11, 10, 30),
                    service_item="腰部调理",
                    note="提前十分钟到店",
                ),
            )
        )
        proposal = asyncio.run(
            self.store.prepare_visit_completion(
                appointment_customer.id,
                visit(
                    visit_date=self.today - timedelta(days=1),
                    complaint="右侧腰部酸胀",
                    risk="绝对禁忌，不做正骨复位，建议前往医院就诊",
                    sessions_used=0,
                    followup_date=self.today,
                ),
            )
        )
        asyncio.run(
            self.store.confirm_visit_completion(
                appointment_customer.id, proposal.confirmation_token
            )
        )

        followup_customer = self._customer(
            "待复诊客户", remaining=3, course="肩颈调理 10 次"
        )
        proposal = asyncio.run(
            self.store.prepare_visit_completion(
                followup_customer.id,
                visit(
                    visit_date=self.today - timedelta(days=2),
                    complaint="肩颈僵硬",
                    risk="适合常规筋膜放松调理",
                    sessions_used=1,
                    followup_date=self.today,
                ),
            )
        )
        asyncio.run(
            self.store.confirm_visit_completion(
                followup_customer.id, proposal.confirmation_token
            )
        )

        risk_customer = self._customer(
            "风险客户", remaining=8, course="全身调理 10 次"
        )
        asyncio.run(
            self.store.add_investigation(
                risk_customer.id,
                visit(
                    visit_date=self.today - timedelta(days=3),
                    complaint="夜间痛醒",
                    risk="相对禁忌，建议医院评估，仅轻柔放松，禁用扳法复位",
                ),
            )
        )

        dashboard = asyncio.run(
            self.store.get_today_dashboard(self.today)
        )
        self.assertEqual(dashboard.appointment_count, 1)
        self.assertEqual(dashboard.followup_count, 2)
        self.assertEqual(dashboard.low_session_count, 2)
        self.assertEqual(dashboard.risk_customer_count, 2)
        self.assertEqual(
            dashboard.today_appointments[0].name, "今日预约客户"
        )
        self.assertEqual(
            dashboard.today_appointments[0].appointment_service, "腰部调理"
        )
        self.assertIsNotNone(
            dashboard.today_appointments[0].last_visit
        )
        self.assertEqual(
            dashboard.risk_customers[0].risk_label, "高风险"
        )
        self.assertTrue(dashboard.recent_visits)

    def test_dashboard_api_returns_sections(self) -> None:
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(
                replace(
                    settings,
                    customer_db_path=Path(temp_dir) / "dashboard-api.sqlite3",
                    tool_audit_db_path=Path(temp_dir) / "audit.sqlite3",
                    staff_access_password="",
                )
            )
            with TestClient(app) as client:
                response = client.get("/api/dashboard/today")
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                for key in (
                    "today_appointments",
                    "due_followups",
                    "low_session_customers",
                    "risk_customers",
                    "recent_visits",
                ):
                    self.assertIn(key, payload)


if __name__ == "__main__":
    unittest.main()
