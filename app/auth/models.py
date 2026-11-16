from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class PortalRegisterInput(BaseModel):
    invite_code: str = Field(min_length=6, max_length=80)
    phone_last4: str = Field(pattern=r"^\d{4}$")
    password: str = Field(min_length=8, max_length=128)
    privacy_consent: bool


class PortalPrivacyPolicy(BaseModel):
    version: str
    purpose: str
    retention: str
    deletion_rule: str
    contact: str


class PortalPrivacyPolicyView(PortalPrivacyPolicy):
    registration_enabled: bool = True
    unavailable_reason: str | None = None


class PortalPrivacyConsent(BaseModel):
    id: str
    account_id: str
    customer_id: str
    policy_version: str
    purpose: str
    retention: str
    deletion_rule: str
    contact: str
    consented_at: datetime


class PortalLoginInput(BaseModel):
    phone: str = Field(min_length=5, max_length=40)
    password: str = Field(min_length=1, max_length=128)


class PortalPasswordChangeInput(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class PortalPasswordResetInput(BaseModel):
    phone: str = Field(min_length=5, max_length=40)
    recovery_code: str = Field(min_length=6, max_length=32)
    new_password: str = Field(min_length=8, max_length=128)


class PortalAccountPasswordInput(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)


class PortalDeletionRequestInput(PortalAccountPasswordInput):
    reason: str = Field(default="", max_length=500)


class StaffLoginInput(BaseModel):
    username: str = Field(min_length=2, max_length=60)
    password: str = Field(min_length=1, max_length=256)


class StaffAccountCreate(BaseModel):
    username: str = Field(min_length=2, max_length=60)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["admin", "therapist"] = "therapist"


class StaffAccountUpdate(BaseModel):
    role: Literal["admin", "therapist"] | None = None
    status: Literal["active", "disabled"] | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class StaffAccount(BaseModel):
    id: str
    username: str
    role: str
    status: str
    created_at: datetime
    last_login_at: datetime | None = None


class StaffActionAudit(BaseModel):
    id: int
    staff_account_id: str | None = None
    staff_username: str
    staff_role: str
    method: str
    path: str
    status_code: int
    created_at: datetime


class LoginAttempt(BaseModel):
    id: int
    role: str
    account_display: str
    ip_address: str
    success: bool
    failure_reason: str | None = None
    retry_after_seconds: int = 0
    created_at: datetime


class PortalInvite(BaseModel):
    invite_code: str
    expires_at: datetime
    portal_path: str = "/customer/"


class PortalRecoveryCode(BaseModel):
    recovery_code: str
    expires_at: datetime


class PortalAccountSnapshot(BaseModel):
    customer_id: str
    customer_name: str
    status: Literal["unbound", "active", "revoked", "deleted"]
    login_phone_masked: str = ""
    created_at: datetime | None = None
    last_login_at: datetime | None = None
    pending_deletion_request_id: str | None = None
    latest_deletion_request_status: Literal[
        "pending", "approved", "rejected", "cancelled"
    ] | None = None


class PortalDeletionRequest(BaseModel):
    id: str
    customer_id: str
    customer_name: str
    login_phone_masked: str = ""
    reason: str = ""
    status: Literal["pending", "approved", "rejected", "cancelled"]
    requested_at: datetime
    processed_at: datetime | None = None
    processed_by: str | None = None
    resolution_note: str = ""


class PortalDeletionResolutionInput(BaseModel):
    action: Literal["approve", "reject"]
    note: str = Field(default="", max_length=500)


class PortalVisit(BaseModel):
    visit_date: date
    visit_type: str
    chief_complaint: str
    care_plan: str
    sessions_used: int


class PortalAppointment(BaseModel):
    scheduled_at: datetime
    service_item: str
    note: str
    status: str


class PortalFollowup(BaseModel):
    due_date: date
    note: str
    status: str


class PortalHome(BaseModel):
    customer_name: str
    phone_masked: str
    selected_course: str
    remaining_sessions: int
    portal_account_status: str = "active"
    latest_deletion_request_status: str | None = None
    appointments: list[PortalAppointment] = Field(default_factory=list)
    followups: list[PortalFollowup] = Field(default_factory=list)
    recent_visits: list[PortalVisit] = Field(default_factory=list)


class PortalScheduleSlot(BaseModel):
    start_at: datetime
    end_at: datetime
    status: str
    is_own: bool = False


class PortalDaySchedule(BaseModel):
    schedule_date: date
    slots: list[PortalScheduleSlot] = Field(default_factory=list)


class AuthSession(BaseModel):
    role: str
    customer_id: str | None = None
    account_id: str | None = None
    staff_username: str | None = None
    staff_role: str | None = None
    expires_at: datetime

