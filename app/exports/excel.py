from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


@dataclass(frozen=True, slots=True)
class ExcelExportResult:
    filename: str
    content: bytes
    customer_count: int
    investigation_count: int
    appointment_count: int
    followup_count: int


class ExcelExporter:
    def __init__(self, customer_db_path: Path) -> None:
        self._db_path = customer_db_path

    async def export(self) -> ExcelExportResult:
        return await asyncio.to_thread(self._export_sync)

    def _export_sync(self) -> ExcelExportResult:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            customers = connection.execute(
                """
                SELECT id, name, gender, age, phone, occupation, address,
                       health_issues, historical_cases, selected_course,
                       remaining_sessions, notes, created_at, updated_at
                FROM customers
                ORDER BY created_at ASC
                """
            ).fetchall()
            investigations = connection.execute(
                """
                SELECT i.*, c.name AS customer_name, c.phone AS customer_phone
                FROM investigations i
                JOIN customers c ON c.id = i.customer_id
                ORDER BY i.visit_date DESC, i.created_at DESC
                """
            ).fetchall()
            appointments = connection.execute(
                """
                SELECT a.*, c.name AS customer_name, c.phone AS customer_phone
                FROM appointments a
                JOIN customers c ON c.id = a.customer_id
                ORDER BY a.scheduled_at DESC
                """
            ).fetchall()
            followups = connection.execute(
                """
                SELECT f.*, c.name AS customer_name, c.phone AS customer_phone
                FROM followup_tasks f
                JOIN customers c ON c.id = f.customer_id
                ORDER BY f.due_date ASC
                """
            ).fetchall()
            handouts = connection.execute(
                """
                SELECT h.*, c.name AS customer_name, c.phone AS customer_phone
                FROM customer_handouts h
                JOIN customers c ON c.id = h.customer_id
                ORDER BY h.updated_at DESC
                """
            ).fetchall()
        finally:
            connection.close()

        workbook = Workbook()
        summary = workbook.active
        summary.title = "导出说明"
        self._write_summary(
            summary,
            customer_count=len(customers),
            investigation_count=len(investigations),
            appointment_count=len(appointments),
            followup_count=len(followups),
        )
        self._write_sheet(
            workbook,
            "客户总表",
            (
                ("客户编号", "id"),
                ("姓名", "name"),
                ("性别", "gender"),
                ("年龄", "age"),
                ("联系电话", "phone"),
                ("职业", "occupation"),
                ("住址", "address"),
                ("现存问题", "health_issues"),
                ("历史病例", "historical_cases"),
                ("所选疗程", "selected_course"),
                ("剩余次数", "remaining_sessions"),
                ("客户备注", "notes"),
                ("建档时间", "created_at"),
                ("更新时间", "updated_at"),
            ),
            customers,
        )
        self._write_sheet(
            workbook,
            "接诊记录",
            (
                ("客户姓名", "customer_name"),
                ("联系电话", "customer_phone"),
                ("接诊日期", "visit_date"),
                ("初诊/复诊", "visit_type"),
                ("主诉", "chief_complaint"),
                ("持续时长", "symptom_duration"),
                ("诱发因素", "trigger"),
                ("现病史", "current_history"),
                ("既往史问询", "medical_history"),
                ("女性专项", "women_special"),
                ("查体记录", "objective_findings"),
                ("风险评估", "risk_assessment"),
                ("调理方案", "care_plan"),
                ("告知登记", "disclosure"),
                ("本次扣次", "sessions_used"),
                ("下次复诊", "followup_date"),
                ("复诊提醒备注", "followup_note"),
                ("复诊反馈", "followup_notes"),
                ("顾客签字", "customer_signature"),
                ("调理师签字", "therapist_signature"),
            ),
            investigations,
        )
        self._write_sheet(
            workbook,
            "预约记录",
            (
                ("客户姓名", "customer_name"),
                ("联系电话", "customer_phone"),
                ("预约时间", "scheduled_at"),
                ("预约项目", "service_item"),
                ("预约备注", "note"),
                ("状态", "status"),
            ),
            appointments,
        )
        self._write_sheet(
            workbook,
            "复诊任务",
            (
                ("客户姓名", "customer_name"),
                ("联系电话", "customer_phone"),
                ("复诊日期", "due_date"),
                ("提醒备注", "note"),
                ("状态", "status"),
                ("完成方式", "completion_type"),
                ("处理备注", "resolution_note"),
                ("处理时间", "completed_at"),
            ),
            followups,
        )
        self._write_sheet(
            workbook,
            "自定义养护说明",
            (
                ("客户姓名", "customer_name"),
                ("联系电话", "customer_phone"),
                ("标题", "title"),
                ("正文", "content"),
                ("更新时间", "updated_at"),
            ),
            handouts,
        )
        buffer = BytesIO()
        workbook.save(buffer)
        now = datetime.now().astimezone()
        return ExcelExportResult(
            filename=f"physio-therapist-data-{now.strftime('%Y%m%d-%H%M%S')}.xlsx",
            content=buffer.getvalue(),
            customer_count=len(customers),
            investigation_count=len(investigations),
            appointment_count=len(appointments),
            followup_count=len(followups),
        )

    @staticmethod
    def _write_summary(
        sheet,
        *,
        customer_count: int,
        investigation_count: int,
        appointment_count: int,
        followup_count: int,
    ) -> None:
        sheet.append(["理疗师业务数据导出"])
        sheet.append(["导出时间", datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")])
        sheet.append(["客户数", customer_count])
        sheet.append(["接诊记录数", investigation_count])
        sheet.append(["预约数", appointment_count])
        sheet.append(["复诊任务数", followup_count])
        sheet.append([])
        sheet.append(["说明", "本文件用于查看和统计，不能替代完整备份恢复。"])
        sheet.column_dimensions["A"].width = 18
        sheet.column_dimensions["B"].width = 52
        sheet["A1"].font = Font(size=18, bold=True, color="FFFFFF")
        sheet["A1"].fill = PatternFill("solid", fgColor="0F6557")
        sheet["A1"].alignment = Alignment(vertical="center")
        sheet.merge_cells("A1:B1")
        sheet.row_dimensions[1].height = 30

    @staticmethod
    def _write_sheet(
        workbook: Workbook,
        title: str,
        columns: Iterable[tuple[str, str]],
        rows: Iterable[sqlite3.Row],
    ) -> None:
        sheet = workbook.create_sheet(title)
        columns = list(columns)
        sheet.append([label for label, _ in columns])
        for row in rows:
            sheet.append(
                [ExcelExporter._safe_cell(row[key]) for _, key in columns]
            )
        header_fill = PatternFill("solid", fgColor="0F6557")
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        for index, (label, _) in enumerate(columns, start=1):
            maximum = len(label)
            for row_index in range(2, min(sheet.max_row, 300) + 1):
                value = sheet.cell(row=row_index, column=index).value
                length = sum(2 if ord(char) > 127 else 1 for char in str(value or ""))
                maximum = max(maximum, length)
            sheet.column_dimensions[get_column_letter(index)].width = min(
                max(12, maximum + 2), 42
            )

    @staticmethod
    def _safe_cell(value):
        if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
            return f"'{value}"
        return value
