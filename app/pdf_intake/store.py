from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from app.memory.base import CustomerNotFoundError
from app.memory.models import InvestigationCreate
from app.pdf_intake.extractor import PdfIntakeError
from app.pdf_intake.models import (
    PdfFieldEdit,
    PdfIntakeConfirmRequest,
    PdfIntakeConfirmResult,
    PdfIntakeEditRecord,
    PdfIntakePreviewResponse,
    PdfPreferenceCandidate,
    PdfPreferenceExample,
    PdfPreferenceOverview,
    PdfPreferenceRecord,
)


_FIELD_LABELS = {
    "customer.name": "姓名",
    "customer.gender": "性别",
    "customer.age": "年龄",
    "customer.phone": "电话",
    "customer.occupation": "职业",
    "customer.address": "住址",
    "customer.health_issues": "现存问题",
    "customer.historical_cases": "历史病例",
    "customer.selected_course": "已选疗程",
    "customer.remaining_sessions": "剩余次数",
    "customer.notes": "客户备注",
    "visit.visit_date": "就诊日期",
    "visit.visit_type": "接诊类型",
    "visit.chief_complaint": "主诉",
    "visit.symptom_duration": "持续时长",
    "visit.trigger": "诱发因素",
    "visit.current_history": "现病史",
    "visit.medical_history": "既往史",
    "visit.women_special": "女性专项",
    "visit.objective_findings": "查体记录",
    "visit.risk_assessment": "风险提示",
    "visit.care_plan": "调理方案",
    "visit.disclosure": "告知登记",
    "visit.customer_signature": "顾客签字",
    "visit.therapist_signature": "理疗师签字",
    "visit.followup_notes": "复诊记录",
    "visit.sessions_used": "使用次数",
    "visit.followup_date": "复诊日期",
    "visit.followup_note": "复诊备注",
}

_MEDICAL_JUDGMENT_FIELDS = {
    "visit.objective_findings",
    "visit.risk_assessment",
    "visit.care_plan",
    "visit.followup_notes",
}

_CLINIC_RULE_FIELDS = {
    "visit.visit_type",
    "visit.disclosure",
    "visit.customer_signature",
    "visit.therapist_signature",
    "visit.sessions_used",
    "visit.followup_date",
}

_EXPRESSION_STYLE_FIELDS = {
    "customer.notes",
    "visit.followup_note",
}

_PREFERENCE_ELIGIBLE_FIELDS = {
    "customer.notes",
    "visit.disclosure",
    "visit.followup_note",
    "visit.visit_type",
}


class PdfIntakeStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    async def save_draft(
        self,
        *,
        preview: PdfIntakePreviewResponse,
        source_pdf: bytes,
        created_by: str,
    ) -> None:
        await asyncio.to_thread(
            self._save_draft_sync, preview, source_pdf, created_by
        )

    async def confirm(
        self,
        request: PdfIntakeConfirmRequest,
        *,
        confirmed_by: str,
    ) -> PdfIntakeConfirmResult:
        return await asyncio.to_thread(
            self._confirm_sync, request, confirmed_by
        )

    async def list_recent_edits(self, limit: int = 20) -> list[PdfIntakeEditRecord]:
        return await asyncio.to_thread(self._list_recent_edits_sync, limit)

    async def get_preference_overview(
        self, therapist_id: str, *, is_admin: bool
    ) -> PdfPreferenceOverview:
        return await asyncio.to_thread(
            self._get_preference_overview_sync,
            therapist_id,
            is_admin,
        )

    async def resolve_preference_candidate(
        self,
        candidate_id: str,
        *,
        therapist_id: str,
        action: str,
        actor: str,
    ) -> None:
        await asyncio.to_thread(
            self._resolve_preference_candidate_sync,
            candidate_id,
            therapist_id,
            action,
            actor,
        )

    async def review_clinic_preference(
        self,
        preference_id: str,
        *,
        action: str,
        approved_by: str,
    ) -> None:
        await asyncio.to_thread(
            self._review_clinic_preference_sync,
            preference_id,
            action,
            approved_by,
        )

    async def list_active_preferences(
        self, therapist_id: str
    ) -> list[PdfPreferenceRecord]:
        return await asyncio.to_thread(
            self._list_active_preferences_sync, therapist_id
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS pdf_intake_drafts (
                    id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    page_count INTEGER NOT NULL,
                    source_pdf BLOB NOT NULL,
                    source_text TEXT NOT NULL,
                    draft_json TEXT NOT NULL,
                    knowledge_json TEXT NOT NULL DEFAULT '[]',
                    edited_json TEXT,
                    extraction_method TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    warnings_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'pending',
                    customer_id TEXT,
                    investigation_id TEXT,
                    followup_id TEXT,
                    created_by TEXT NOT NULL,
                    confirmed_by TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    confirmed_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_pdf_intake_status_expiry
                    ON pdf_intake_drafts(status, expires_at);

                CREATE TABLE IF NOT EXISTS pdf_intake_edit_records (
                    id TEXT PRIMARY KEY,
                    draft_id TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    customer_id TEXT NOT NULL,
                    investigation_id TEXT NOT NULL,
                    changed_by TEXT NOT NULL,
                    edits_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_pdf_intake_edits_created
                    ON pdf_intake_edit_records(created_at DESC);

                CREATE TABLE IF NOT EXISTS pdf_intake_preferences (
                    id TEXT PRIMARY KEY,
                    therapist_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    task_type TEXT NOT NULL DEFAULT 'pdf_intake',
                    field_path TEXT NOT NULL,
                    field_label TEXT NOT NULL,
                    category TEXT NOT NULL,
                    change_kind TEXT NOT NULL,
                    rule_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_candidate_id TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    approved_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_pdf_intake_preferences_status
                    ON pdf_intake_preferences(
                        status, scope, therapist_id, updated_at DESC
                    );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_pdf_intake_preferences_source
                    ON pdf_intake_preferences(source_candidate_id, scope);

                CREATE TABLE IF NOT EXISTS pdf_intake_preference_decisions (
                    candidate_id TEXT PRIMARY KEY,
                    therapist_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    preference_id TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(pdf_intake_drafts)"
                ).fetchall()
            }
            if "knowledge_json" not in columns:
                connection.execute(
                    """
                    ALTER TABLE pdf_intake_drafts
                    ADD COLUMN knowledge_json TEXT NOT NULL DEFAULT '[]'
                    """
                )
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            connection.execute(
                """
                DELETE FROM pdf_intake_drafts
                WHERE status = 'pending' AND expires_at < ?
                """,
                (now,),
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _save_draft_sync(
        self,
        preview: PdfIntakePreviewResponse,
        source_pdf: bytes,
        created_by: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=24)
        draft_json = json.dumps(
            {
                "customer": preview.customer.model_dump(),
                "visit": preview.visit.model_dump(mode="json"),
            },
            ensure_ascii=False,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO pdf_intake_drafts (
                    id, file_name, sha256, file_size, page_count, source_pdf,
                    source_text, draft_json, knowledge_json, extraction_method,
                    provider, warnings_json, created_by, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    preview.draft_id,
                    preview.file_name,
                    preview.sha256,
                    preview.file_size,
                    preview.page_count,
                    source_pdf,
                    preview.source_text,
                    draft_json,
                    json.dumps(
                        [
                            item.model_dump(mode="json")
                            for item in preview.knowledge_assistance
                        ],
                        ensure_ascii=False,
                    ),
                    preview.extraction_method,
                    preview.provider,
                    json.dumps(preview.warnings, ensure_ascii=False),
                    created_by,
                    now.isoformat(timespec="seconds"),
                    expires_at.isoformat(timespec="seconds"),
                ),
            )

    def _confirm_sync(
        self,
        request: PdfIntakeConfirmRequest,
        confirmed_by: str,
    ) -> PdfIntakeConfirmResult:
        if request.visit.sessions_used:
            raise PdfIntakeError(
                "sessions_not_supported",
                "PDF 智能录入只保存接诊记录，不扣减疗程次数；扣次请使用接诊确认",
            )
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            draft = connection.execute(
                """
                SELECT status, expires_at, customer_id, investigation_id,
                       followup_id, file_name, draft_json
                FROM pdf_intake_drafts WHERE id = ?
                """,
                (request.draft_id,),
            ).fetchone()
            if draft is None:
                raise PdfIntakeError("draft_not_found", "PDF 草稿不存在")
            if draft["status"] != "pending":
                raise PdfIntakeError(
                    "already_confirmed", "该 PDF 草稿已经确认录入"
                )
            expires_at = datetime.fromisoformat(draft["expires_at"])
            if expires_at < now:
                raise PdfIntakeError(
                    "draft_expired", "PDF 草稿已超过 24 小时，请重新上传"
                )

            created_customer = request.customer_id is None
            if created_customer:
                customer_id = self._insert_customer(connection, request)
            else:
                customer_id = request.customer_id or ""
                exists = connection.execute(
                    "SELECT 1 FROM customers WHERE id = ?",
                    (customer_id,),
                ).fetchone()
                if exists is None:
                    raise CustomerNotFoundError(f"客户不存在: {customer_id}")

            investigation_id = self._insert_investigation(
                connection, customer_id, request.visit
            )
            edit_record_id = None
            if request.remember_edits:
                field_edits = self._build_field_edits(
                    draft["draft_json"],
                    request,
                    include_customer=created_customer,
                )
                if field_edits:
                    edit_record_id = str(uuid.uuid4())
                    connection.execute(
                        """
                        INSERT INTO pdf_intake_edit_records (
                            id, draft_id, file_name, customer_id,
                            investigation_id, changed_by, edits_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            edit_record_id,
                            request.draft_id,
                            draft["file_name"],
                            customer_id,
                            investigation_id,
                            confirmed_by,
                            json.dumps(
                                [
                                    edit.model_dump(mode="json")
                                    for edit in field_edits
                                ],
                                ensure_ascii=False,
                            ),
                            now.isoformat(timespec="seconds"),
                        ),
                    )
            followup_id = None
            if request.visit.followup_date:
                followup_id = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO followup_tasks (
                        id, customer_id, investigation_id, due_date, note,
                        status, completion_type, resolution_note, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'pending', NULL, '', ?)
                    """,
                    (
                        followup_id,
                        customer_id,
                        investigation_id,
                        request.visit.followup_date.isoformat(),
                        request.visit.followup_note or "PDF 智能录入生成的复诊任务",
                        now.isoformat(timespec="seconds"),
                    ),
                )

            edited_json = json.dumps(
                {
                    "customer": (
                        request.customer.model_dump()
                        if request.customer is not None
                        else None
                    ),
                    "visit": request.visit.model_dump(mode="json"),
                    "remember_edits": request.remember_edits,
                },
                ensure_ascii=False,
            )
            connection.execute(
                """
                UPDATE pdf_intake_drafts
                SET status = 'confirmed', edited_json = ?, customer_id = ?,
                    investigation_id = ?, followup_id = ?, confirmed_by = ?,
                    confirmed_at = ?
                WHERE id = ?
                """,
                (
                    edited_json,
                    customer_id,
                    investigation_id,
                    followup_id,
                    confirmed_by,
                    now.isoformat(timespec="seconds"),
                    request.draft_id,
                ),
            )
        return PdfIntakeConfirmResult(
            draft_id=request.draft_id,
            customer_id=customer_id,
            investigation_id=investigation_id,
            followup_id=followup_id,
            created_customer=created_customer,
            edit_record_id=edit_record_id,
        )

    def _list_recent_edits_sync(
        self, limit: int
    ) -> list[PdfIntakeEditRecord]:
        safe_limit = max(1, min(100, limit))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, draft_id, file_name, customer_id,
                       investigation_id, changed_by, edits_json, created_at
                FROM pdf_intake_edit_records
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        records: list[PdfIntakeEditRecord] = []
        for row in rows:
            edits = [
                PdfFieldEdit(**item)
                for item in json.loads(row["edits_json"])
            ]
            records.append(
                PdfIntakeEditRecord(
                    id=row["id"],
                    draft_id=row["draft_id"],
                    file_name=row["file_name"],
                    customer_id=row["customer_id"],
                    investigation_id=row["investigation_id"],
                    changed_by=row["changed_by"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    edits=edits,
                )
            )
        return records

    def _get_preference_overview_sync(
        self, therapist_id: str, is_admin: bool
    ) -> PdfPreferenceOverview:
        with self._connect() as connection:
            candidates = self._list_preference_candidates_sync(
                connection, therapist_id
            )
            active_preferences = self._query_preferences_sync(
                connection,
                """
                status = 'active'
                AND (scope = 'clinic' OR therapist_id = ?)
                """,
                (therapist_id,),
            )
            if is_admin:
                pending_clinic_rules = self._query_preferences_sync(
                    connection,
                    "scope = 'clinic' AND status = 'pending_admin'",
                    (),
                )
            else:
                pending_clinic_rules = self._query_preferences_sync(
                    connection,
                    """
                    scope = 'clinic' AND status = 'pending_admin'
                    AND created_by = ?
                    """,
                    (therapist_id,),
                )
        return PdfPreferenceOverview(
            candidates=candidates,
            active_preferences=active_preferences,
            pending_clinic_rules=pending_clinic_rules,
        )

    def _list_preference_candidates_sync(
        self,
        connection: sqlite3.Connection,
        therapist_id: str,
    ) -> list[PdfPreferenceCandidate]:
        edit_rows = connection.execute(
            """
            SELECT file_name, changed_by, edits_json, created_at
            FROM pdf_intake_edit_records
            WHERE changed_by = ?
            ORDER BY created_at DESC
            LIMIT 200
            """,
            (therapist_id,),
        ).fetchall()
        if not edit_rows:
            return []

        existing_preferences = connection.execute(
            """
            SELECT scope, therapist_id, field_path, change_kind, status
            FROM pdf_intake_preferences
            WHERE status IN ('active', 'pending_admin')
            """
        ).fetchall()
        covered_personal: set[tuple[str, str, str]] = set()
        covered_clinic: set[tuple[str, str, str]] = set()
        for preference in existing_preferences:
            key = (
                preference["field_path"],
                preference["change_kind"],
                preference["status"],
            )
            if preference["scope"] == "clinic":
                covered_clinic.add(key)
            elif preference["therapist_id"] == therapist_id:
                covered_personal.add(key)

        decided_ids = {
            row["candidate_id"]
            for row in connection.execute(
                """
                SELECT candidate_id
                FROM pdf_intake_preference_decisions
                WHERE therapist_id = ?
                """,
                (therapist_id,),
            ).fetchall()
        }
        grouped: dict[
            tuple[str, str, str],
            list[PdfPreferenceExample],
        ] = {}
        for row in edit_rows:
            created_at = datetime.fromisoformat(row["created_at"])
            for raw_edit in json.loads(row["edits_json"]):
                path = raw_edit.get("path", "")
                if path not in _PREFERENCE_ELIGIBLE_FIELDS:
                    continue
                category = _edit_category(path)
                if category not in {"expression_style", "clinic_rule"}:
                    continue
                change_kind = _change_kind(
                    str(raw_edit.get("before", "")),
                    str(raw_edit.get("after", "")),
                )
                key = (path, category, change_kind)
                examples = grouped.setdefault(key, [])
                if len(examples) < 3:
                    examples.append(
                        PdfPreferenceExample(
                            before=str(raw_edit.get("before", "")),
                            after=str(raw_edit.get("after", "")),
                            file_name=row["file_name"],
                            created_at=created_at,
                        )
                    )

        candidates: list[PdfPreferenceCandidate] = []
        for (path, category, change_kind), examples in grouped.items():
            if len(examples) < 2:
                continue
            coverage_key = (path, change_kind, "active")
            pending_key = (path, change_kind, "pending_admin")
            if (
                coverage_key in covered_clinic
                or pending_key in covered_clinic
                or coverage_key in covered_personal
                or pending_key in covered_personal
            ):
                continue
            candidate_id = _candidate_id(
                therapist_id, path, category, change_kind
            )
            if candidate_id in decided_ids:
                continue
            label = _FIELD_LABELS[path]
            candidates.append(
                PdfPreferenceCandidate(
                    id=candidate_id,
                    field_path=path,
                    field_label=label,
                    category=category,
                    change_kind=change_kind,
                    occurrence_count=len(examples),
                    proposed_rule=_preference_rule(label, change_kind),
                    examples=examples,
                )
            )
        return sorted(
            candidates,
            key=lambda item: (-item.occurrence_count, item.field_path),
        )

    def _resolve_preference_candidate_sync(
        self,
        candidate_id: str,
        therapist_id: str,
        action: str,
        actor: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            decision = connection.execute(
                """
                SELECT 1 FROM pdf_intake_preference_decisions
                WHERE candidate_id = ?
                """,
                (candidate_id,),
            ).fetchone()
            if decision is not None:
                raise PdfIntakeError(
                    "preference_already_resolved", "该偏好建议已经处理"
                )
            candidates = self._list_preference_candidates_sync(
                connection, therapist_id
            )
            candidate = next(
                (item for item in candidates if item.id == candidate_id),
                None,
            )
            if candidate is None:
                raise PdfIntakeError(
                    "preference_candidate_not_found",
                    "偏好建议不存在或已失效",
                )
            preference_id = None
            if action in {"remember_therapist", "submit_clinic_rule"}:
                preference_id = str(uuid.uuid4())
                scope = (
                    "therapist"
                    if action == "remember_therapist"
                    else "clinic"
                )
                status = (
                    "active"
                    if action == "remember_therapist"
                    else "pending_admin"
                )
                connection.execute(
                    """
                    INSERT INTO pdf_intake_preferences (
                        id, therapist_id, scope, field_path, field_label,
                        category, change_kind, rule_text, status,
                        source_candidate_id, created_by, approved_by,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        preference_id,
                        therapist_id,
                        scope,
                        candidate.field_path,
                        candidate.field_label,
                        candidate.category,
                        candidate.change_kind,
                        candidate.proposed_rule,
                        status,
                        candidate.id,
                        actor,
                        actor if scope == "therapist" else None,
                        now.isoformat(timespec="seconds"),
                        now.isoformat(timespec="seconds"),
                    ),
                )
            elif action != "only_once":
                raise PdfIntakeError(
                    "invalid_preference_action", "无法识别偏好处理方式"
                )
            connection.execute(
                """
                INSERT INTO pdf_intake_preference_decisions (
                    candidate_id, therapist_id, action, preference_id,
                    created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    candidate.id,
                    therapist_id,
                    action,
                    preference_id,
                    now.isoformat(timespec="seconds"),
                ),
            )

    def _review_clinic_preference_sync(
        self,
        preference_id: str,
        action: str,
        approved_by: str,
    ) -> None:
        if action not in {"approve", "reject"}:
            raise PdfIntakeError(
                "invalid_preference_action", "无法识别门店规则审核动作"
            )
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT scope, status FROM pdf_intake_preferences
                WHERE id = ?
                """,
                (preference_id,),
            ).fetchone()
            if row is None:
                raise PdfIntakeError(
                    "preference_not_found", "门店规则不存在"
                )
            if row["scope"] != "clinic" or row["status"] != "pending_admin":
                raise PdfIntakeError(
                    "preference_not_pending",
                    "该门店规则不在待审核状态",
                )
            connection.execute(
                """
                UPDATE pdf_intake_preferences
                SET status = ?, approved_by = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    "active" if action == "approve" else "rejected",
                    approved_by if action == "approve" else None,
                    now,
                    preference_id,
                ),
            )

    def _list_active_preferences_sync(
        self, therapist_id: str
    ) -> list[PdfPreferenceRecord]:
        with self._connect() as connection:
            return self._query_preferences_sync(
                connection,
                """
                status = 'active'
                AND (scope = 'clinic' OR therapist_id = ?)
                """,
                (therapist_id,),
            )

    @staticmethod
    def _query_preferences_sync(
        connection: sqlite3.Connection,
        where_clause: str,
        parameters: tuple,
    ) -> list[PdfPreferenceRecord]:
        rows = connection.execute(
            f"""
            SELECT id, therapist_id, scope, task_type, field_path,
                   field_label, category, change_kind, rule_text, status,
                   created_by, approved_by, created_at, updated_at
            FROM pdf_intake_preferences
            WHERE {where_clause}
            ORDER BY
                CASE scope WHEN 'clinic' THEN 0 ELSE 1 END,
                updated_at DESC
            """,
            parameters,
        ).fetchall()
        return [
            PdfPreferenceRecord(
                id=row["id"],
                therapist_id=row["therapist_id"],
                scope=row["scope"],
                task_type=row["task_type"],
                field_path=row["field_path"],
                field_label=row["field_label"],
                category=row["category"],
                change_kind=row["change_kind"],
                rule_text=row["rule_text"],
                status=row["status"],
                created_by=row["created_by"],
                approved_by=row["approved_by"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    @staticmethod
    def _build_field_edits(
        original_json: str,
        request: PdfIntakeConfirmRequest,
        *,
        include_customer: bool,
    ) -> list[PdfFieldEdit]:
        original = json.loads(original_json)
        original_customer = original.get("customer") or {}
        original_visit = original.get("visit") or {}
        final_customer = (
            request.customer.model_dump()
            if include_customer and request.customer is not None
            else {}
        )
        final_visit = request.visit.model_dump(mode="json")
        sections = (
            (
                "customer",
                original_customer,
                final_customer,
                include_customer,
            ),
            ("visit", original_visit, final_visit, True),
        )
        edits: list[PdfFieldEdit] = []
        for section, before_values, after_values, enabled in sections:
            if not enabled:
                continue
            for field in _ordered_field_names(section):
                path = f"{section}.{field}"
                if path not in _FIELD_LABELS:
                    continue
                before = _display_value(before_values.get(field))
                after = _display_value(after_values.get(field))
                if before.strip() == after.strip():
                    continue
                edits.append(
                    PdfFieldEdit(
                        path=path,
                        label=_FIELD_LABELS[path],
                        category=_edit_category(path),
                        before=before,
                        after=after,
                    )
                )
        return edits

    @staticmethod
    def _insert_customer(
        connection: sqlite3.Connection,
        request: PdfIntakeConfirmRequest,
    ) -> str:
        assert request.customer is not None
        customer_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        values = request.customer.model_dump()
        connection.execute(
            """
            INSERT INTO customers (
                id, name, gender, age, phone, occupation, address,
                health_issues, historical_cases, selected_course,
                remaining_sessions, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                values["name"].strip(),
                values["gender"].strip(),
                values["age"].strip(),
                values["phone"].strip(),
                values["occupation"].strip(),
                values["address"].strip(),
                values["health_issues"].strip(),
                values["historical_cases"].strip(),
                values["selected_course"].strip(),
                values["remaining_sessions"],
                values["notes"].strip(),
                now,
                now,
            ),
        )
        return customer_id

    @staticmethod
    def _insert_investigation(
        connection: sqlite3.Connection,
        customer_id: str,
        visit: InvestigationCreate,
    ) -> str:
        investigation_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        values = visit.model_dump()
        connection.execute(
            """
            INSERT INTO investigations (
                id, customer_id, visit_date, visit_type, chief_complaint,
                symptom_duration, trigger, current_history, medical_history,
                women_special, objective_findings, risk_assessment,
                care_plan, disclosure, customer_signature,
                therapist_signature, followup_notes, sessions_used,
                followup_date, followup_note, created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                investigation_id,
                customer_id,
                visit.visit_date.isoformat(),
                values["visit_type"].strip(),
                values["chief_complaint"].strip(),
                values["symptom_duration"].strip(),
                values["trigger"].strip(),
                values["current_history"].strip(),
                values["medical_history"].strip(),
                values["women_special"].strip(),
                values["objective_findings"].strip(),
                values["risk_assessment"].strip(),
                values["care_plan"].strip(),
                values["disclosure"].strip(),
                values["customer_signature"].strip(),
                values["therapist_signature"].strip(),
                values["followup_notes"].strip(),
                visit.sessions_used,
                (
                    visit.followup_date.isoformat()
                    if visit.followup_date
                    else None
                ),
                values["followup_note"].strip(),
                now,
                now,
            ),
        )
        return investigation_id


def _ordered_field_names(section: str) -> list[str]:
    prefix = f"{section}."
    return [
        path.removeprefix(prefix)
        for path in _FIELD_LABELS
        if path.startswith(prefix)
    ]


def _display_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _edit_category(path: str) -> str:
    if path in _MEDICAL_JUDGMENT_FIELDS:
        return "medical_judgment"
    if path in _CLINIC_RULE_FIELDS:
        return "clinic_rule"
    if path in _EXPRESSION_STYLE_FIELDS:
        return "expression_style"
    return "customer_fact"


def _change_kind(before: str, after: str) -> str:
    if not before.strip() and after.strip():
        return "addition"
    if before.strip() and not after.strip():
        return "deletion"
    return "rewrite"


def _candidate_id(
    therapist_id: str,
    field_path: str,
    category: str,
    change_kind: str,
) -> str:
    raw = f"{therapist_id}|{field_path}|{category}|{change_kind}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _preference_rule(field_label: str, change_kind: str) -> str:
    if change_kind == "addition":
        return (
            f"生成“{field_label}”时，在原文信息支持的情况下补充这类固定内容。"
        )
    if change_kind == "deletion":
        return f"生成“{field_label}”时，默认删减这类非必要内容。"
    return f"生成“{field_label}”时，采用更简洁、明确的固定表达。"
