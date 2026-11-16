from __future__ import annotations

import asyncio
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.config import get_settings
from app.memory.models import CustomerHandoutUpdate, InvestigationCreate


class ExcelExportTests(unittest.TestCase):
    def test_therapist_excel_contains_business_sheets_and_is_audited(self) -> None:
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            audit_path = temp_path / "audit.sqlite3"
            app = create_app(
                replace(
                    settings,
                    customer_db_path=temp_path / "excel.sqlite3",
                    tool_audit_db_path=audit_path,
                    backup_dir=temp_path / "backups",
                    backup_auto_enabled=False,
                    staff_access_password="",
                )
            )
            with TestClient(app) as client:
                customer = client.post(
                    "/api/customers",
                    json={
                        "name": "Excel客户",
                        "phone": "13800005555",
                        "selected_course": "腰部调理 10 次",
                        "remaining_sessions": 6,
                    },
                ).json()
                asyncio.run(
                    app.state.customer_memory.add_investigation(
                        customer["id"],
                        InvestigationCreate(
                            visit_date=date(2026, 11, 12),
                            chief_complaint="右侧腰部酸胀",
                            risk_assessment="适合常规筋膜放松调理",
                            care_plan="注意保暖",
                            sessions_used=1,
                        ),
                    )
                )
                asyncio.run(
                    app.state.customer_memory.save_customer_handout(
                        customer["id"],
                        CustomerHandoutUpdate(
                            title="自定义养护说明",
                            content="这是可以导出的自定义内容。",
                        ),
                    )
                )
                client.post(
                    f"/api/customers/{customer['id']}/appointments",
                    json={
                        "scheduled_at": "2026-11-16T09:30",
                        "service_item": "腰部调理",
                    },
                )
                response = client.get("/api/exports/excel")
                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    "spreadsheetml.sheet",
                    response.headers["content-type"],
                )
                workbook = load_workbook(BytesIO(response.content))
                self.assertEqual(
                    set(workbook.sheetnames),
                    {
                        "导出说明",
                        "客户总表",
                        "接诊记录",
                        "预约记录",
                        "复诊任务",
                        "自定义养护说明",
                    },
                )
                customer_values = [
                    value
                    for row in workbook["客户总表"].iter_rows(
                        min_row=2, values_only=True
                    )
                    for value in row
                ]
                self.assertIn("Excel客户", customer_values)
                visit_values = [
                    value
                    for row in workbook["接诊记录"].iter_rows(
                        min_row=2, values_only=True
                    )
                    for value in row
                ]
                self.assertIn("右侧腰部酸胀", visit_values)
                handout_values = [
                    value
                    for row in workbook["自定义养护说明"].iter_rows(
                        min_row=2, values_only=True
                    )
                    for value in row
                ]
                self.assertIn("这是可以导出的自定义内容。", handout_values)
                all_values = {
                    str(cell.value)
                    for sheet in workbook.worksheets
                    for row in sheet.iter_rows()
                    for cell in row
                    if cell.value is not None
                }
                self.assertFalse(
                    any("password_hash" in value for value in all_values)
                )
                self.assertFalse(
                    any("physio_customer_session" in value for value in all_values)
                )

            connection = sqlite3.connect(audit_path)
            try:
                audit = connection.execute(
                    """
                    SELECT status FROM tool_audit
                    WHERE tool_name = 'export_therapist_excel'
                    ORDER BY started_at DESC LIMIT 1
                    """
                ).fetchone()
            finally:
                connection.close()
            self.assertEqual(audit[0], "success")

    def test_excel_export_requires_staff_login_when_password_enabled(self) -> None:
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            app = create_app(
                replace(
                    settings,
                    customer_db_path=temp_path / "protected-excel.sqlite3",
                    tool_audit_db_path=temp_path / "audit.sqlite3",
                    backup_dir=temp_path / "backups",
                    backup_auto_enabled=False,
                    staff_access_password="excel-staff-pass",
                )
            )
            with TestClient(app) as client:
                self.assertEqual(
                    client.get("/api/exports/excel").status_code, 401
                )
                login = client.post(
                    "/api/staff/login",
                    json={
                        "username": "admin",
                        "password": "excel-staff-pass",
                    },
                )
                self.assertEqual(login.status_code, 200)
                self.assertEqual(
                    client.get("/api/exports/excel").status_code, 200
                )


if __name__ == "__main__":
    unittest.main()
