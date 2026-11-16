from __future__ import annotations

from datetime import date
from typing import Protocol

from app.memory.models import (
    AppointmentCreate,
    AppointmentRecord,
    AppointmentSlotRecord,
    AppointmentStatusUpdate,
    CustomerCreate,
    CustomerDetail,
    CustomerHandoutUpdate,
    CustomerMessageDraft,
    CustomerMemoryContext,
    CustomerProfile,
    CustomerUpdate,
    InvestigationCreate,
    InvestigationRecord,
    DaySchedule,
    FollowupTask,
    FollowupStatusUpdate,
    VisitCompletionProposal,
    VisitCompletionResult,
    TodayDashboard,
    ScheduleWindow,
    SlotAppointmentCreate,
)


class CustomerNotFoundError(LookupError):
    """Raised when a requested customer does not exist."""


class VisitCompletionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CustomerMemoryStore(Protocol):
    async def create_customer(self, payload: CustomerCreate) -> CustomerProfile: ...

    async def update_customer(
        self, customer_id: str, payload: CustomerUpdate
    ) -> CustomerProfile: ...

    async def list_customers(self, query: str = "") -> list[CustomerProfile]: ...

    async def get_customer(self, customer_id: str) -> CustomerProfile: ...

    async def get_customer_detail(self, customer_id: str) -> CustomerDetail: ...

    async def add_investigation(
        self, customer_id: str, payload: InvestigationCreate
    ) -> InvestigationRecord: ...

    async def list_investigations(
        self, customer_id: str
    ) -> list[InvestigationRecord]: ...

    async def delete_investigation(
        self, customer_id: str, investigation_id: str
    ) -> bool: ...

    async def prepare_visit_completion(
        self, customer_id: str, payload: InvestigationCreate
    ) -> VisitCompletionProposal: ...

    async def confirm_visit_completion(
        self, customer_id: str, confirmation_token: str
    ) -> VisitCompletionResult: ...

    async def list_followups(
        self, customer_id: str
    ) -> list[FollowupTask]: ...

    async def update_followup_status(
        self,
        customer_id: str,
        followup_id: str,
        payload: FollowupStatusUpdate,
    ) -> FollowupTask: ...

    async def create_appointment(
        self, customer_id: str, payload: AppointmentCreate
    ) -> AppointmentRecord: ...

    async def list_appointments(
        self, customer_id: str
    ) -> list[AppointmentRecord]: ...

    async def configure_day_schedule(
        self, window: ScheduleWindow
    ) -> DaySchedule: ...

    async def get_day_schedule(self, target_date: date) -> DaySchedule: ...

    async def update_slot_status(
        self, slot_id: str, status: str
    ) -> AppointmentSlotRecord: ...

    async def schedule_customer_slot(
        self, customer_id: str, payload: SlotAppointmentCreate
    ) -> AppointmentRecord: ...

    async def update_appointment_status(
        self,
        customer_id: str,
        appointment_id: str,
        status: str,
    ) -> AppointmentRecord: ...

    async def get_today_dashboard(
        self,
        target_date: date,
        *,
        low_session_threshold: int = 2,
        risk_days: int = 30,
    ) -> TodayDashboard: ...

    async def get_customer_script(
        self, customer_id: str
    ) -> CustomerMessageDraft: ...

    async def get_customer_handout(
        self, customer_id: str
    ) -> CustomerMessageDraft: ...

    async def save_customer_handout(
        self, customer_id: str, payload: CustomerHandoutUpdate
    ) -> CustomerMessageDraft: ...

    async def reset_customer_handout(
        self, customer_id: str
    ) -> CustomerMessageDraft: ...

    async def build_context(
        self,
        customer_id: str,
        query: str,
        *,
        recent_limit: int = 2,
        relevant_limit: int = 2,
    ) -> CustomerMemoryContext: ...

    async def count_customers(self) -> int: ...

