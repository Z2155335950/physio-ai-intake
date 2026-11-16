from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.memory.models import CustomerCreate, InvestigationCreate


class PdfCustomerDraft(BaseModel):
    name: str = ""
    gender: str = ""
    age: str = ""
    phone: str = ""
    occupation: str = ""
    address: str = ""
    health_issues: str = ""
    historical_cases: str = ""
    selected_course: str = ""
    remaining_sessions: int = Field(default=0, ge=0, le=10000)
    notes: str = ""

    def to_customer_create(self) -> CustomerCreate:
        values = self.model_dump()
        for field in (
            "name",
            "gender",
            "age",
            "phone",
            "occupation",
            "address",
            "health_issues",
            "historical_cases",
            "selected_course",
            "notes",
        ):
            values[field] = str(values[field]).strip()
        return CustomerCreate(**values)


class PdfVisitDraft(BaseModel):
    visit_date: date
    visit_type: str = "初诊"
    chief_complaint: str = ""
    symptom_duration: str = ""
    trigger: str = ""
    current_history: str = ""
    medical_history: str = ""
    women_special: str = ""
    objective_findings: str = ""
    risk_assessment: str = ""
    care_plan: str = ""
    disclosure: str = ""
    customer_signature: str = ""
    therapist_signature: str = ""
    followup_notes: str = ""
    sessions_used: int = Field(default=0, ge=0, le=100)
    followup_date: date | None = None
    followup_note: str = ""


class PdfIntakeDraft(BaseModel):
    customer: PdfCustomerDraft = Field(default_factory=PdfCustomerDraft)
    visit: PdfVisitDraft


class PdfIntakePreviewResponse(BaseModel):
    draft_id: str
    file_name: str
    sha256: str
    file_size: int
    page_count: int
    extraction_method: Literal["ai", "local"]
    provider: str
    source_text: str
    customer: PdfCustomerDraft
    visit: PdfVisitDraft
    field_confidence: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    applied_preferences: list[str] = Field(default_factory=list)
    knowledge_assistance: list["PdfKnowledgeItem"] = Field(
        default_factory=list
    )


class PdfIntakeConfirmRequest(BaseModel):
    draft_id: str = Field(min_length=1, max_length=100)
    customer_id: str | None = Field(default=None, max_length=100)
    customer: CustomerCreate | None = None
    visit: InvestigationCreate
    remember_edits: bool = True

    @model_validator(mode="after")
    def require_customer_for_new_record(self) -> "PdfIntakeConfirmRequest":
        if not self.customer_id and self.customer is None:
            raise ValueError("新客户录入必须提供客户资料")
        return self


class PdfIntakeConfirmResult(BaseModel):
    draft_id: str
    customer_id: str
    investigation_id: str
    followup_id: str | None = None
    created_customer: bool
    edit_record_id: str | None = None
    status: Literal["confirmed"] = "confirmed"


EditCategory = Literal[
    "expression_style",
    "customer_fact",
    "clinic_rule",
    "medical_judgment",
]


class PdfFieldEdit(BaseModel):
    path: str
    label: str
    category: EditCategory
    before: str = ""
    after: str = ""


class PdfIntakeEditRecord(BaseModel):
    id: str
    draft_id: str
    file_name: str
    customer_id: str
    investigation_id: str
    changed_by: str
    created_at: datetime
    edits: list[PdfFieldEdit] = Field(default_factory=list)


class PdfPreferenceExample(BaseModel):
    before: str = ""
    after: str = ""
    file_name: str
    created_at: datetime


class PdfPreferenceCandidate(BaseModel):
    id: str
    field_path: str
    field_label: str
    category: EditCategory
    change_kind: Literal["addition", "deletion", "rewrite"]
    occurrence_count: int
    proposed_rule: str
    examples: list[PdfPreferenceExample] = Field(default_factory=list)


class PdfPreferenceRecord(BaseModel):
    id: str
    therapist_id: str
    scope: Literal["therapist", "clinic"]
    task_type: str
    field_path: str
    field_label: str
    category: EditCategory
    change_kind: Literal["addition", "deletion", "rewrite"]
    rule_text: str
    status: Literal["active", "pending_admin", "rejected", "disabled"]
    created_by: str
    approved_by: str | None = None
    created_at: datetime
    updated_at: datetime


class PdfPreferenceOverview(BaseModel):
    candidates: list[PdfPreferenceCandidate] = Field(default_factory=list)
    active_preferences: list[PdfPreferenceRecord] = Field(default_factory=list)
    pending_clinic_rules: list[PdfPreferenceRecord] = Field(
        default_factory=list
    )


class PdfPreferenceResolveRequest(BaseModel):
    action: Literal["only_once", "remember_therapist", "submit_clinic_rule"]


class PdfPreferenceReviewRequest(BaseModel):
    action: Literal["approve", "reject"]


class PdfKnowledgeReference(BaseModel):
    index: int
    title: str
    source: str
    excerpt: str
    score: float
    authority_level: str = "D"
    authority_label: str = "未分级来源"


class PdfKnowledgeItem(BaseModel):
    topic: Literal[
        "risk_notice",
        "communication_script",
        "customer_handout",
        "draft_completion",
    ]
    label: str
    found: bool
    text: str
    references: list[PdfKnowledgeReference] = Field(default_factory=list)
