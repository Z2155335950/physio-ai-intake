from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    gender: str = Field(default="", max_length=20)
    age: str = Field(default="", max_length=20)
    phone: str = Field(default="", max_length=40)
    occupation: str = Field(default="", max_length=100)
    address: str = Field(default="", max_length=300)
    health_issues: str = Field(default="", max_length=4000)
    historical_cases: str = Field(default="", max_length=8000)
    selected_course: str = Field(default="", max_length=300)
    remaining_sessions: int = Field(default=0, ge=0, le=10000)
    notes: str = Field(default="", max_length=2000)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    gender: str | None = Field(default=None, max_length=20)
    age: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=40)
    occupation: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=300)
    health_issues: str | None = Field(default=None, max_length=4000)
    historical_cases: str | None = Field(default=None, max_length=8000)
    selected_course: str | None = Field(default=None, max_length=300)
    remaining_sessions: int | None = Field(default=None, ge=0, le=10000)
    notes: str | None = Field(default=None, max_length=2000)


class CustomerProfile(BaseModel):
    id: str
    name: str
    gender: str
    age: str
    phone: str
    occupation: str
    address: str
    health_issues: str
    historical_cases: str
    selected_course: str
    remaining_sessions: int
    notes: str
    created_at: datetime
    updated_at: datetime


class InvestigationCreate(BaseModel):
    visit_date: date
    visit_type: str = Field(default="初诊", max_length=20)
    chief_complaint: str = Field(min_length=1, max_length=3000)
    symptom_duration: str = Field(default="", max_length=500)
    trigger: str = Field(default="", max_length=500)
    current_history: str = Field(default="", max_length=4000)
    medical_history: str = Field(default="", max_length=4000)
    women_special: str = Field(default="", max_length=2000)
    objective_findings: str = Field(default="", max_length=4000)
    risk_assessment: str = Field(default="", max_length=2000)
    care_plan: str = Field(default="", max_length=4000)
    disclosure: str = Field(default="", max_length=2000)
    customer_signature: str = Field(default="", max_length=120)
    therapist_signature: str = Field(default="", max_length=120)
    followup_notes: str = Field(default="", max_length=3000)
    sessions_used: int = Field(default=0, ge=0, le=100)
    followup_date: date | None = None
    followup_note: str = Field(default="", max_length=2000)


class InvestigationRecord(InvestigationCreate):
    id: str
    customer_id: str
    created_at: datetime
    updated_at: datetime


class CustomerQuickSummary(BaseModel):
    health_issues: str
    historical_cases: str
    major_risk: str
    major_risk_level: Literal["none", "caution", "high"] = "none"
    selected_course: str
    remaining_sessions: int
    latest_visit_date: date | None = None
    last_chief_complaint: str = ""
    last_followup_feedback: str = ""
    recent_danger_signal: str = ""
    danger_signal_date: date | None = None


class CustomerDetail(BaseModel):
    customer: CustomerProfile
    quick_summary: CustomerQuickSummary
    investigations: list[InvestigationRecord] = Field(default_factory=list)
    followups: list["FollowupTask"] = Field(default_factory=list)
    appointments: list["AppointmentRecord"] = Field(default_factory=list)


class FollowupTask(BaseModel):
    id: str
    customer_id: str
    investigation_id: str
    due_date: date
    note: str
    status: str
    completion_type: str | None = None
    resolution_note: str = ""
    created_at: datetime
    completed_at: datetime | None = None


class FollowupStatusUpdate(BaseModel):
    status: Literal["pending", "completed", "deferred", "cancelled"]
    completion_type: Literal["visited", "phone_followup"] | None = None
    resolution_note: str = Field(default="", max_length=2000)


class AppointmentCreate(BaseModel):
    scheduled_at: datetime
    service_item: str = Field(default="", max_length=300)
    note: str = Field(default="", max_length=2000)
    status: Literal["scheduled", "completed", "cancelled"] = "scheduled"


class AppointmentRecord(AppointmentCreate):
    id: str
    customer_id: str
    slot_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ScheduleWindow(BaseModel):
    schedule_date: date
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    interval_minutes: int = Field(default=60, ge=15, le=180)


class AppointmentSlotRecord(BaseModel):
    id: str
    schedule_date: date
    start_at: datetime
    end_at: datetime
    status: Literal["available", "closed", "booked", "completed"]
    appointment_id: str | None = None
    customer_id: str | None = None
    customer_name: str | None = None
    service_item: str = ""
    note: str = ""


class DaySchedule(BaseModel):
    schedule_date: date
    slots: list[AppointmentSlotRecord] = Field(default_factory=list)


class SlotStatusUpdate(BaseModel):
    status: Literal["available", "closed"]


class SlotAppointmentCreate(BaseModel):
    slot_id: str = Field(min_length=1, max_length=100)
    service_item: str = Field(default="", max_length=300)
    note: str = Field(default="", max_length=2000)


class AppointmentStatusUpdate(BaseModel):
    status: Literal["completed", "cancelled"]


class LastVisitSummary(BaseModel):
    investigation_id: str
    visit_date: date
    visit_type: str
    chief_complaint: str
    risk_assessment: str
    care_plan: str
    followup_notes: str
    sessions_used: int


class WorkbenchCustomer(BaseModel):
    customer_id: str
    name: str
    phone: str
    age: str
    health_issues: str
    selected_course: str
    remaining_sessions: int
    last_visit: LastVisitSummary | None = None
    scheduled_at: datetime | None = None
    appointment_service: str | None = None
    followup_due_date: date | None = None
    followup_note: str | None = None
    risk_label: str | None = None


class TodayDashboard(BaseModel):
    as_of: date
    appointment_count: int
    followup_count: int
    low_session_count: int
    risk_customer_count: int
    today_appointments: list[WorkbenchCustomer] = Field(default_factory=list)
    due_followups: list[WorkbenchCustomer] = Field(default_factory=list)
    low_session_customers: list[WorkbenchCustomer] = Field(default_factory=list)
    risk_customers: list[WorkbenchCustomer] = Field(default_factory=list)
    recent_visits: list[WorkbenchCustomer] = Field(default_factory=list)


class CustomerMessageDraft(BaseModel):
    title: str
    content: str
    is_customized: bool = False


class CustomerHandoutUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=12000)


class VisitCompletionProposal(BaseModel):
    confirmation_token: str
    expires_at: datetime
    customer_id: str
    customer_name: str
    visit_date: date
    visit_type: str
    chief_complaint: str
    sessions_used: int
    previous_remaining_sessions: int
    proposed_remaining_sessions: int
    followup_date: date | None = None


class VisitCompletionResult(BaseModel):
    customer_id: str
    investigation: InvestigationRecord
    previous_remaining_sessions: int
    remaining_sessions: int
    followup_task: FollowupTask | None = None


class CustomerMemoryContext(BaseModel):
    customer: CustomerProfile
    records: list[InvestigationRecord] = Field(default_factory=list)

    def render_for_prompt(
        self, *, include_pii: bool = False
    ) -> tuple[str, list[str]]:
        if not include_pii:
            return self._render_minimized(), [
                "客户姓名",
                "联系电话",
                "住址",
                "精确年龄",
                "职业",
                "客户自由备注",
                "签字信息",
            ]
        return self._render_full(), [
            "联系电话",
            "住址",
            "签字信息",
        ]

    def _render_minimized(self) -> str:
        lines = [
            "## 当前客户纵向记忆（严格客户隔离｜已脱敏）",
            f"匿名客户编号：C-{self.customer.id[:8]}",
            f"年龄段：{self._age_band(self.customer.age)}",
            f"疗程剩余次数：{self.customer.remaining_sessions} 次",
        ]
        if self.customer.selected_course:
            lines.append(f"已选疗程：{self.customer.selected_course}")
        if self.customer.health_issues:
            lines.append(
                f"现存问题摘要：{self._clip(self.customer.health_issues, 500)}"
            )
        if self.customer.historical_cases:
            lines.append(
                f"历史病例摘要：{self._clip(self.customer.historical_cases, 700)}"
            )
        if not self.records:
            lines.append("该客户暂无接诊调查记录。")
        else:
            lines.append(
                "以下只是当前客户的历史接诊记录，不是诊断结论；引用时注明记录日期。"
            )
        self._append_records(lines)
        return "\n".join(lines)

    def _render_full(self) -> str:
        lines = [
            "## 当前客户纵向记忆（严格客户隔离）",
            f"客户ID：{self.customer.id}",
            f"客户：{self.customer.name}；性别：{self.customer.gender or '未记录'}；"
            f"年龄：{self.customer.age or '未记录'}；"
            f"职业：{self.customer.occupation or '未记录'}。",
        ]
        if self.customer.notes:
            lines.append(f"客户备注：{self._clip(self.customer.notes, 300)}")
        if self.customer.health_issues:
            lines.append(
                f"客户现存问题：{self._clip(self.customer.health_issues, 600)}"
            )
        if self.customer.historical_cases:
            lines.append(
                f"历史病例：{self._clip(self.customer.historical_cases, 900)}"
            )
        if self.customer.selected_course:
            lines.append(f"已选疗程：{self.customer.selected_course}")
        lines.append(f"疗程剩余次数：{self.customer.remaining_sessions} 次")
        if not self.records:
            lines.append("该客户暂无接诊调查记录。")
        else:
            lines.append(
                "以下只是当前客户的历史接诊记录，不是诊断结论；引用时注明记录日期。"
            )
        self._append_records(lines)
        return "\n".join(lines)

    def _append_records(self, lines: list[str]) -> None:
        for record in self.records:
            lines.append(
                f"【接诊 {record.visit_date.isoformat()}｜{record.visit_type}】"
            )
            fields = (
                ("主诉", record.chief_complaint),
                ("持续时长", record.symptom_duration),
                ("诱发因素", record.trigger),
                ("现病史", record.current_history),
                ("既往史问询", record.medical_history),
                ("女性专项", record.women_special),
                ("查体记录", record.objective_findings),
                ("风险评估", record.risk_assessment),
                ("调理方案", record.care_plan),
                ("告知登记", record.disclosure),
                ("复诊备注", record.followup_notes),
            )
            for label, value in fields:
                if value:
                    lines.append(f"- {label}：{self._clip(value, 600)}")
            if sum(len(line) for line in lines) > 12000:
                lines.append("其余较早记录已省略，避免超出当前上下文预算。")
                break

    @staticmethod
    def _clip(value: str, limit: int) -> str:
        return value if len(value) <= limit else f"{value[:limit].rstrip()}…"

    @staticmethod
    def _age_band(age: str) -> str:
        match = re.search(r"\d{1,3}", age or "")
        if not match:
            return "未记录"
        value = int(match.group(0))
        if value < 18:
            return "18岁以下"
        if value < 30:
            return "18～29岁"
        if value < 40:
            return "30～39岁"
        if value < 50:
            return "40～49岁"
        if value < 60:
            return "50～59岁"
        if value < 70:
            return "60～69岁"
        if value < 80:
            return "70～79岁"
        return "80岁及以上"

