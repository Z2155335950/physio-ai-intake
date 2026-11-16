from __future__ import annotations

import asyncio
import hashlib
import re
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from app.memory.base import CustomerNotFoundError, VisitCompletionError
from app.memory.models import (
    AppointmentCreate,
    AppointmentRecord,
    AppointmentSlotRecord,
    AppointmentStatusUpdate,
    CustomerCreate,
    CustomerDetail,
    CustomerMemoryContext,
    CustomerProfile,
    CustomerQuickSummary,
    CustomerMessageDraft,
    CustomerHandoutUpdate,
    CustomerUpdate,
    FollowupTask,
    FollowupStatusUpdate,
    InvestigationCreate,
    InvestigationRecord,
    LastVisitSummary,
    DaySchedule,
    ScheduleWindow,
    SlotAppointmentCreate,
    TodayDashboard,
    VisitCompletionProposal,
    VisitCompletionResult,
    WorkbenchCustomer,
)
from app.text import tokenize


_CUSTOMER_COLUMNS = (
    "id, name, gender, age, phone, occupation, address, health_issues, "
    "historical_cases, selected_course, remaining_sessions, notes, "
    "created_at, updated_at"
)
_INVESTIGATION_COLUMNS = (
    "id, customer_id, visit_date, visit_type, chief_complaint, "
    "symptom_duration, trigger, current_history, medical_history, "
    "women_special, objective_findings, risk_assessment, care_plan, "
    "disclosure, customer_signature, therapist_signature, followup_notes, "
    "sessions_used, followup_date, followup_note, "
    "created_at, updated_at"
)


class SqliteCustomerMemoryStore:
    """Persistent customer profiles and visit records with hard customer scope."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    async def create_customer(self, payload: CustomerCreate) -> CustomerProfile:
        return await asyncio.to_thread(self._create_customer_sync, payload)

    async def update_customer(
        self, customer_id: str, payload: CustomerUpdate
    ) -> CustomerProfile:
        return await asyncio.to_thread(
            self._update_customer_sync, customer_id, payload
        )

    async def list_customers(self, query: str = "") -> list[CustomerProfile]:
        return await asyncio.to_thread(self._list_customers_sync, query)

    async def get_customer(self, customer_id: str) -> CustomerProfile:
        return await asyncio.to_thread(self._get_customer_sync, customer_id)

    async def get_customer_detail(self, customer_id: str) -> CustomerDetail:
        return await asyncio.to_thread(self._get_customer_detail_sync, customer_id)

    async def add_investigation(
        self, customer_id: str, payload: InvestigationCreate
    ) -> InvestigationRecord:
        return await asyncio.to_thread(
            self._add_investigation_sync, customer_id, payload
        )

    async def list_investigations(
        self, customer_id: str
    ) -> list[InvestigationRecord]:
        return await asyncio.to_thread(
            self._list_investigations_sync, customer_id
        )

    async def delete_investigation(
        self, customer_id: str, investigation_id: str
    ) -> bool:
        return await asyncio.to_thread(
            self._delete_investigation_sync, customer_id, investigation_id
        )

    async def prepare_visit_completion(
        self, customer_id: str, payload: InvestigationCreate
    ) -> VisitCompletionProposal:
        return await asyncio.to_thread(
            self._prepare_visit_completion_sync, customer_id, payload
        )

    async def confirm_visit_completion(
        self, customer_id: str, confirmation_token: str
    ) -> VisitCompletionResult:
        return await asyncio.to_thread(
            self._confirm_visit_completion_sync,
            customer_id,
            confirmation_token,
        )

    async def list_followups(
        self, customer_id: str
    ) -> list[FollowupTask]:
        return await asyncio.to_thread(self._list_followups_sync, customer_id)

    async def update_followup_status(
        self,
        customer_id: str,
        followup_id: str,
        payload: FollowupStatusUpdate,
    ) -> FollowupTask:
        return await asyncio.to_thread(
            self._update_followup_status_sync,
            customer_id,
            followup_id,
            payload,
        )

    async def create_appointment(
        self, customer_id: str, payload: AppointmentCreate
    ) -> AppointmentRecord:
        return await asyncio.to_thread(
            self._create_appointment_sync, customer_id, payload
        )

    async def list_appointments(
        self, customer_id: str
    ) -> list[AppointmentRecord]:
        return await asyncio.to_thread(
            self._list_appointments_sync, customer_id
        )

    async def configure_day_schedule(
        self, window: ScheduleWindow
    ) -> DaySchedule:
        return await asyncio.to_thread(
            self._configure_day_schedule_sync, window
        )

    async def get_day_schedule(self, target_date: date) -> DaySchedule:
        return await asyncio.to_thread(
            self._get_day_schedule_sync, target_date
        )

    async def update_slot_status(
        self, slot_id: str, status: str
    ) -> AppointmentSlotRecord:
        return await asyncio.to_thread(
            self._update_slot_status_sync, slot_id, status
        )

    async def schedule_customer_slot(
        self, customer_id: str, payload: SlotAppointmentCreate
    ) -> AppointmentRecord:
        return await asyncio.to_thread(
            self._schedule_customer_slot_sync, customer_id, payload
        )

    async def update_appointment_status(
        self,
        customer_id: str,
        appointment_id: str,
        status: str,
    ) -> AppointmentRecord:
        return await asyncio.to_thread(
            self._update_appointment_status_sync,
            customer_id,
            appointment_id,
            status,
        )

    async def get_today_dashboard(
        self,
        target_date: date,
        *,
        low_session_threshold: int = 2,
        risk_days: int = 30,
    ) -> TodayDashboard:
        return await asyncio.to_thread(
            self._get_today_dashboard_sync,
            target_date,
            low_session_threshold,
            risk_days,
        )

    async def get_customer_script(
        self, customer_id: str
    ) -> CustomerMessageDraft:
        return await asyncio.to_thread(
            self._get_customer_script_sync, customer_id
        )

    async def get_customer_handout(
        self, customer_id: str
    ) -> CustomerMessageDraft:
        return await asyncio.to_thread(
            self._get_customer_handout_sync, customer_id
        )

    async def save_customer_handout(
        self, customer_id: str, payload: CustomerHandoutUpdate
    ) -> CustomerMessageDraft:
        return await asyncio.to_thread(
            self._save_customer_handout_sync, customer_id, payload
        )

    async def reset_customer_handout(
        self, customer_id: str
    ) -> CustomerMessageDraft:
        return await asyncio.to_thread(
            self._reset_customer_handout_sync, customer_id
        )

    async def build_context(
        self,
        customer_id: str,
        query: str,
        *,
        recent_limit: int = 2,
        relevant_limit: int = 2,
    ) -> CustomerMemoryContext:
        return await asyncio.to_thread(
            self._build_context_sync,
            customer_id,
            query,
            recent_limit,
            relevant_limit,
        )

    async def count_customers(self) -> int:
        return await asyncio.to_thread(self._count_customers_sync)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    gender TEXT NOT NULL DEFAULT '',
                    age TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    occupation TEXT NOT NULL DEFAULT '',
                    address TEXT NOT NULL DEFAULT '',
                    health_issues TEXT NOT NULL DEFAULT '',
                    historical_cases TEXT NOT NULL DEFAULT '',
                    selected_course TEXT NOT NULL DEFAULT '',
                    remaining_sessions INTEGER NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS investigations (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    visit_date TEXT NOT NULL,
                    visit_type TEXT NOT NULL,
                    chief_complaint TEXT NOT NULL,
                    symptom_duration TEXT NOT NULL DEFAULT '',
                    trigger TEXT NOT NULL DEFAULT '',
                    current_history TEXT NOT NULL DEFAULT '',
                    medical_history TEXT NOT NULL DEFAULT '',
                    women_special TEXT NOT NULL DEFAULT '',
                    objective_findings TEXT NOT NULL DEFAULT '',
                    risk_assessment TEXT NOT NULL DEFAULT '',
                    care_plan TEXT NOT NULL DEFAULT '',
                    disclosure TEXT NOT NULL DEFAULT '',
                    customer_signature TEXT NOT NULL DEFAULT '',
                    therapist_signature TEXT NOT NULL DEFAULT '',
                    followup_notes TEXT NOT NULL DEFAULT '',
                    sessions_used INTEGER NOT NULL DEFAULT 0,
                    followup_date TEXT,
                    followup_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_investigations_customer_date
                    ON investigations(customer_id, visit_date DESC, created_at DESC);

                CREATE TABLE IF NOT EXISTS followup_tasks (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    investigation_id TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    completion_type TEXT,
                    resolution_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (investigation_id) REFERENCES investigations(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_followups_customer_due
                    ON followup_tasks(customer_id, status, due_date);

                CREATE TABLE IF NOT EXISTS appointments (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    slot_id TEXT,
                    scheduled_at TEXT NOT NULL,
                    service_item TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'scheduled',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_appointments_date
                    ON appointments(status, scheduled_at);

                CREATE TABLE IF NOT EXISTS appointment_slots (
                    id TEXT PRIMARY KEY,
                    schedule_date TEXT NOT NULL,
                    start_at TEXT NOT NULL UNIQUE,
                    end_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'available',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_appointment_slots_date
                    ON appointment_slots(schedule_date, start_at);

                CREATE TABLE IF NOT EXISTS customer_handouts (
                    customer_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS visit_completion_challenges (
                    token_hash TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    sessions_used INTEGER NOT NULL,
                    previous_remaining INTEGER NOT NULL,
                    proposed_remaining INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    confirmed_at TEXT,
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_visit_challenges_customer
                    ON visit_completion_challenges(customer_id, status, expires_at);
                """
            )
            self._ensure_customer_columns(connection)
            self._ensure_investigation_columns(connection)
            self._ensure_appointment_columns(connection)
            self._ensure_followup_columns(connection)

    @staticmethod
    def _ensure_customer_columns(connection: sqlite3.Connection) -> None:
        existing_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(customers)").fetchall()
        }
        migrations = {
            "health_issues": "TEXT NOT NULL DEFAULT ''",
            "historical_cases": "TEXT NOT NULL DEFAULT ''",
            "selected_course": "TEXT NOT NULL DEFAULT ''",
            "remaining_sessions": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, definition in migrations.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE customers ADD COLUMN {column} {definition}"
                )

    @staticmethod
    def _ensure_investigation_columns(connection: sqlite3.Connection) -> None:
        existing_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(investigations)"
            ).fetchall()
        }
        migrations = {
            "sessions_used": "INTEGER NOT NULL DEFAULT 0",
            "followup_date": "TEXT",
            "followup_note": "TEXT NOT NULL DEFAULT ''",
        }
        for column, definition in migrations.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE investigations ADD COLUMN {column} {definition}"
                )

    @staticmethod
    def _ensure_appointment_columns(connection: sqlite3.Connection) -> None:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(appointments)"
            ).fetchall()
        }
        if "slot_id" not in columns:
            connection.execute("ALTER TABLE appointments ADD COLUMN slot_id TEXT")

    @staticmethod
    def _ensure_followup_columns(connection: sqlite3.Connection) -> None:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(followup_tasks)"
            ).fetchall()
        }
        migrations = {
            "completion_type": "TEXT",
            "resolution_note": "TEXT NOT NULL DEFAULT ''",
        }
        for column, definition in migrations.items():
            if column not in columns:
                connection.execute(
                    f"ALTER TABLE followup_tasks ADD COLUMN {column} {definition}"
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

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _create_customer_sync(self, payload: CustomerCreate) -> CustomerProfile:
        customer_id = str(uuid.uuid4())
        now = self._now()
        values = payload.model_dump()
        with self._connect() as connection:
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
        return self._get_customer_sync(customer_id)

    def _update_customer_sync(
        self, customer_id: str, payload: CustomerUpdate
    ) -> CustomerProfile:
        updates = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not updates:
            return self._get_customer_sync(customer_id)
        self._get_customer_sync(customer_id)

        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = [
            value.strip() if isinstance(value, str) else value
            for value in updates.values()
        ]
        with self._connect() as connection:
            connection.execute(
                f"UPDATE customers SET {assignments}, updated_at = ? WHERE id = ?",
                (*values, self._now(), customer_id),
            )
        return self._get_customer_sync(customer_id)

    def _list_customers_sync(self, query: str) -> list[CustomerProfile]:
        normalized = query.strip()
        with self._connect() as connection:
            if normalized:
                pattern = f"%{normalized}%"
                rows = connection.execute(
                    f"""
                    SELECT {_CUSTOMER_COLUMNS} FROM customers
                    WHERE name LIKE ? OR phone LIKE ? OR notes LIKE ?
                       OR health_issues LIKE ? OR historical_cases LIKE ?
                       OR selected_course LIKE ?
                    ORDER BY updated_at DESC
                    """,
                    (pattern, pattern, pattern, pattern, pattern, pattern),
                ).fetchall()
            else:
                rows = connection.execute(
                    f"""
                    SELECT {_CUSTOMER_COLUMNS} FROM customers
                    ORDER BY updated_at DESC
                    """
                ).fetchall()
        return [self._customer_from_row(row) for row in rows]

    def _get_customer_sync(self, customer_id: str) -> CustomerProfile:
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT {_CUSTOMER_COLUMNS} FROM customers WHERE id = ?",
                (customer_id,),
            ).fetchone()
        if row is None:
            raise CustomerNotFoundError(f"客户不存在: {customer_id}")
        return self._customer_from_row(row)

    def _get_customer_detail_sync(self, customer_id: str) -> CustomerDetail:
        customer = self._get_customer_sync(customer_id)
        records = self._list_investigations_sync(customer_id)
        followups = self._list_followups_sync(customer_id)
        appointments = self._list_appointments_sync(customer_id)
        return CustomerDetail(
            customer=customer,
            quick_summary=self._build_quick_summary(customer, records),
            investigations=records,
            followups=followups,
            appointments=appointments,
        )

    def _add_investigation_sync(
        self, customer_id: str, payload: InvestigationCreate
    ) -> InvestigationRecord:
        self._get_customer_sync(customer_id)
        with self._connect() as connection:
            investigation_id = self._insert_investigation(
                connection, customer_id, payload
            )
        return self._get_investigation_sync(customer_id, investigation_id)

    def _prepare_visit_completion_sync(
        self, customer_id: str, payload: InvestigationCreate
    ) -> VisitCompletionProposal:
        customer = self._get_customer_sync(customer_id)
        self._validate_visit_sessions(payload, customer.remaining_sessions)
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(minutes=10)
        proposed_remaining = (
            customer.remaining_sessions - payload.sessions_used
        )
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM visit_completion_challenges
                WHERE customer_id = ? AND status = 'pending' AND expires_at < ?
                """,
                (customer_id, created_at.isoformat(timespec="seconds")),
            )
            connection.execute(
                """
                INSERT INTO visit_completion_challenges (
                    token_hash, customer_id, payload_json, sessions_used,
                    previous_remaining, proposed_remaining, status,
                    created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    token_hash,
                    customer_id,
                    payload.model_dump_json(),
                    payload.sessions_used,
                    customer.remaining_sessions,
                    proposed_remaining,
                    created_at.isoformat(timespec="seconds"),
                    expires_at.isoformat(timespec="seconds"),
                ),
            )
        return VisitCompletionProposal(
            confirmation_token=raw_token,
            expires_at=expires_at,
            customer_id=customer.id,
            customer_name=customer.name,
            visit_date=payload.visit_date,
            visit_type=payload.visit_type,
            chief_complaint=payload.chief_complaint,
            sessions_used=payload.sessions_used,
            previous_remaining_sessions=customer.remaining_sessions,
            proposed_remaining_sessions=proposed_remaining,
            followup_date=payload.followup_date,
        )

    def _confirm_visit_completion_sync(
        self, customer_id: str, confirmation_token: str
    ) -> VisitCompletionResult:
        token_hash = hashlib.sha256(
            confirmation_token.encode("utf-8")
        ).hexdigest()
        now = datetime.now(timezone.utc)
        investigation_id: str | None = None
        followup_id: str | None = None
        previous_remaining = 0
        proposed_remaining = 0
        payload: InvestigationCreate | None = None

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            challenge = connection.execute(
                """
                SELECT payload_json, sessions_used, previous_remaining,
                       proposed_remaining, status, expires_at
                FROM visit_completion_challenges
                WHERE token_hash = ? AND customer_id = ?
                """,
                (token_hash, customer_id),
            ).fetchone()
            if challenge is None:
                raise VisitCompletionError(
                    "confirmation_not_found", "确认信息不存在或客户不匹配"
                )
            if challenge["status"] != "pending":
                raise VisitCompletionError(
                    "confirmation_used", "该确认令牌已使用或失效"
                )
            expires_at = datetime.fromisoformat(challenge["expires_at"])
            if expires_at < now:
                raise VisitCompletionError(
                    "confirmation_expired", "确认已过期，请重新生成"
                )

            customer_row = connection.execute(
                "SELECT remaining_sessions FROM customers WHERE id = ?",
                (customer_id,),
            ).fetchone()
            if customer_row is None:
                raise CustomerNotFoundError(f"客户不存在: {customer_id}")
            current_remaining = int(customer_row["remaining_sessions"])
            previous_remaining = int(challenge["previous_remaining"])
            if current_remaining != previous_remaining:
                raise VisitCompletionError(
                    "stale_confirmation",
                    "客户剩余次数已变化，请重新生成确认信息",
                )

            payload = InvestigationCreate.model_validate_json(
                challenge["payload_json"]
            )
            self._validate_visit_sessions(payload, current_remaining)
            proposed_remaining = (
                current_remaining - payload.sessions_used
            )
            investigation_id = self._insert_investigation(
                connection, customer_id, payload
            )
            connection.execute(
                """
                UPDATE customers
                SET remaining_sessions = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    proposed_remaining,
                    now.isoformat(timespec="seconds"),
                    customer_id,
                ),
            )
            if payload.followup_date:
                followup_id = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO followup_tasks (
                        id, customer_id, investigation_id, due_date, note,
                        status, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'pending', ?)
                    """,
                    (
                        followup_id,
                        customer_id,
                        investigation_id,
                        payload.followup_date.isoformat(),
                        payload.followup_note.strip(),
                        now.isoformat(timespec="seconds"),
                    ),
                )
            connection.execute(
                """
                UPDATE visit_completion_challenges
                SET status = 'confirmed', confirmed_at = ?
                WHERE token_hash = ?
                """,
                (now.isoformat(timespec="seconds"), token_hash),
            )

        if investigation_id is None or payload is None:
            raise VisitCompletionError(
                "completion_failed", "接诊完成事务未生成有效记录"
            )
        investigation = self._get_investigation_sync(
            customer_id, investigation_id
        )
        followup = (
            self._get_followup_sync(customer_id, followup_id)
            if followup_id
            else None
        )
        return VisitCompletionResult(
            customer_id=customer_id,
            investigation=investigation,
            previous_remaining_sessions=previous_remaining,
            remaining_sessions=proposed_remaining,
            followup_task=followup,
        )

    def _insert_investigation(
        self,
        connection: sqlite3.Connection,
        customer_id: str,
        payload: InvestigationCreate,
    ) -> str:
        investigation_id = str(uuid.uuid4())
        now = self._now()
        values = payload.model_dump()
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
                payload.visit_date.isoformat(),
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
                payload.sessions_used,
                (
                    payload.followup_date.isoformat()
                    if payload.followup_date
                    else None
                ),
                payload.followup_note.strip(),
                now,
                now,
            ),
        )
        return investigation_id

    @staticmethod
    def _validate_visit_sessions(
        payload: InvestigationCreate, current_remaining: int
    ) -> None:
        if payload.sessions_used > current_remaining:
            raise VisitCompletionError(
                "insufficient_sessions",
                f"剩余次数不足：当前 {current_remaining} 次，"
                f"本次需要使用 {payload.sessions_used} 次",
            )
        if (
            payload.sessions_used > 0
            and "绝对禁忌" in payload.risk_assessment
        ):
            raise VisitCompletionError(
                "absolute_contraindication",
                "风险评估为绝对禁忌时不能扣减疗程次数",
            )

    def _get_investigation_sync(
        self, customer_id: str, investigation_id: str
    ) -> InvestigationRecord:
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT {_INVESTIGATION_COLUMNS} FROM investigations
                WHERE id = ? AND customer_id = ?
                """,
                (investigation_id, customer_id),
            ).fetchone()
        if row is None:
            raise CustomerNotFoundError(
                f"当前客户下不存在该接诊记录: {investigation_id}"
            )
        return self._investigation_from_row(row)

    def _list_investigations_sync(
        self, customer_id: str
    ) -> list[InvestigationRecord]:
        self._get_customer_sync(customer_id)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT {_INVESTIGATION_COLUMNS} FROM investigations
                WHERE customer_id = ?
                ORDER BY visit_date DESC, created_at DESC
                """,
                (customer_id,),
            ).fetchall()
        return [self._investigation_from_row(row) for row in rows]

    def _delete_investigation_sync(
        self, customer_id: str, investigation_id: str
    ) -> bool:
        self._get_customer_sync(customer_id)
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM investigations WHERE id = ? AND customer_id = ?",
                (investigation_id, customer_id),
            )
        return cursor.rowcount > 0

    def _list_followups_sync(self, customer_id: str) -> list[FollowupTask]:
        self._get_customer_sync(customer_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, customer_id, investigation_id, due_date, note,
                       status, completion_type, resolution_note,
                       created_at, completed_at
                FROM followup_tasks
                WHERE customer_id = ?
                ORDER BY
                    CASE status WHEN 'pending' THEN 0 ELSE 1 END,
                    due_date ASC,
                    created_at DESC
                """,
                (customer_id,),
            ).fetchall()
        return [self._followup_from_row(row) for row in rows]

    def _get_followup_sync(
        self, customer_id: str, followup_id: str
    ) -> FollowupTask:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, customer_id, investigation_id, due_date, note,
                       status, completion_type, resolution_note,
                       created_at, completed_at
                FROM followup_tasks
                WHERE id = ? AND customer_id = ?
                """,
                (followup_id, customer_id),
            ).fetchone()
        if row is None:
            raise VisitCompletionError(
                "followup_not_found", "复诊任务不存在"
            )
        return self._followup_from_row(row)

    def _update_followup_status_sync(
        self,
        customer_id: str,
        followup_id: str,
        payload: FollowupStatusUpdate,
    ) -> FollowupTask:
        if payload.status == "completed" and not payload.completion_type:
            raise VisitCompletionError(
                "completion_type_required",
                "完成复诊任务时必须选择完成方式",
            )
        if payload.status != "completed" and payload.completion_type:
            raise VisitCompletionError(
                "invalid_completion_type",
                "只有已完成任务可以设置完成方式",
            )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT status FROM followup_tasks
                WHERE id = ? AND customer_id = ?
                """,
                (followup_id, customer_id),
            ).fetchone()
            if row is None:
                raise VisitCompletionError(
                    "followup_not_found", "复诊任务不存在"
                )
            current = row["status"]
            if current in {"completed", "cancelled"}:
                raise VisitCompletionError(
                    "followup_finished",
                    "该复诊任务已经完成或取消，不能再次修改",
                )
            if payload.status == "pending" and current != "deferred":
                raise VisitCompletionError(
                    "invalid_followup_transition",
                    "只有暂时不来的任务可以恢复为待复诊",
                )
            completed_at = (
                None
                if payload.status == "pending"
                else datetime.now(timezone.utc).isoformat(timespec="seconds")
            )
            connection.execute(
                """
                UPDATE followup_tasks
                SET status = ?, completion_type = ?, resolution_note = ?,
                    completed_at = ?
                WHERE id = ? AND customer_id = ?
                """,
                (
                    payload.status,
                    payload.completion_type,
                    payload.resolution_note.strip(),
                    completed_at,
                    followup_id,
                    customer_id,
                ),
            )
        return self._get_followup_sync(customer_id, followup_id)

    def _create_appointment_sync(
        self, customer_id: str, payload: AppointmentCreate
    ) -> AppointmentRecord:
        self._get_customer_sync(customer_id)
        appointment_id = str(uuid.uuid4())
        now = self._now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO appointments (
                    id, customer_id, slot_id, scheduled_at, service_item, note,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    appointment_id,
                    customer_id,
                    None,
                    self._normalize_local_datetime(payload.scheduled_at),
                    payload.service_item.strip(),
                    payload.note.strip(),
                    payload.status.strip() or "scheduled",
                    now,
                    now,
                ),
            )
        return self._get_appointment_sync(customer_id, appointment_id)

    def _get_appointment_sync(
        self, customer_id: str, appointment_id: str
    ) -> AppointmentRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, customer_id, slot_id, scheduled_at, service_item, note,
                       status, created_at, updated_at
                FROM appointments
                WHERE id = ? AND customer_id = ?
                """,
                (appointment_id, customer_id),
            ).fetchone()
        if row is None:
            raise VisitCompletionError(
                "appointment_not_found", "预约记录不存在"
            )
        return self._appointment_from_row(row)

    def _list_appointments_sync(
        self, customer_id: str
    ) -> list[AppointmentRecord]:
        self._get_customer_sync(customer_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, customer_id, slot_id, scheduled_at, service_item, note,
                       status, created_at, updated_at
                FROM appointments
                WHERE customer_id = ?
                ORDER BY scheduled_at ASC
                """,
                (customer_id,),
            ).fetchall()
        return [self._appointment_from_row(row) for row in rows]

    def _configure_day_schedule_sync(
        self, window: ScheduleWindow
    ) -> DaySchedule:
        start_time = datetime.strptime(window.start_time, "%H:%M").time()
        end_time = datetime.strptime(window.end_time, "%H:%M").time()
        start_at = datetime.combine(window.schedule_date, start_time)
        end_at = datetime.combine(window.schedule_date, end_time)
        if end_at <= start_at:
            raise VisitCompletionError(
                "invalid_schedule", "结束时间必须晚于开始时间"
            )
        interval = timedelta(minutes=window.interval_minutes)
        now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            booked_rows = connection.execute(
                """
                SELECT start_at FROM appointment_slots
                WHERE schedule_date = ? AND status = 'booked'
                """,
                (window.schedule_date.isoformat(),),
            ).fetchall()
            booked_starts = {row["start_at"] for row in booked_rows}
            connection.execute(
                """
                DELETE FROM appointment_slots
                WHERE schedule_date = ? AND status != 'booked'
                """,
                (window.schedule_date.isoformat(),),
            )
            cursor = start_at
            while cursor + interval <= end_at:
                start_value = self._normalize_local_datetime(cursor)
                if start_value not in booked_starts:
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO appointment_slots (
                            id, schedule_date, start_at, end_at, status,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 'available', ?, ?)
                        """,
                        (
                            str(uuid.uuid4()),
                            window.schedule_date.isoformat(),
                            start_value,
                            self._normalize_local_datetime(cursor + interval),
                            now,
                            now,
                        ),
                    )
                cursor += interval
        return self._get_day_schedule_sync(window.schedule_date)

    def _get_day_schedule_sync(self, target_date: date) -> DaySchedule:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT s.id, s.schedule_date, s.start_at, s.end_at, s.status,
                       a.id AS appointment_id, a.customer_id,
                       c.name AS customer_name, a.service_item, a.note
                FROM appointment_slots s
                LEFT JOIN appointments a
                    ON a.slot_id = s.id
                   AND a.status IN ('scheduled', 'completed')
                LEFT JOIN customers c ON c.id = a.customer_id
                WHERE s.schedule_date = ?
                ORDER BY s.start_at ASC
                """,
                (target_date.isoformat(),),
            ).fetchall()
        return DaySchedule(
            schedule_date=target_date,
            slots=[self._slot_from_row(row) for row in rows],
        )

    def _update_slot_status_sync(
        self, slot_id: str, status: str
    ) -> AppointmentSlotRecord:
        if status not in {"available", "closed"}:
            raise VisitCompletionError(
                "invalid_slot_status", "时段只能设为可预约或关闭"
            )
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM appointment_slots WHERE id = ?",
                (slot_id,),
            ).fetchone()
            if row is None:
                raise VisitCompletionError(
                    "slot_not_found", "预约时段不存在"
                )
            if row["status"] == "booked":
                raise VisitCompletionError(
                    "slot_booked", "已预约时段不能关闭"
                )
            connection.execute(
                """
                UPDATE appointment_slots
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, self._now(), slot_id),
            )
        return self._get_slot_sync(slot_id)

    def _schedule_customer_slot_sync(
        self, customer_id: str, payload: SlotAppointmentCreate
    ) -> AppointmentRecord:
        appointment_id = str(uuid.uuid4())
        now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            customer = connection.execute(
                "SELECT id FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()
            if customer is None:
                raise CustomerNotFoundError(f"客户不存在: {customer_id}")
            slot = connection.execute(
                """
                SELECT id, start_at, status FROM appointment_slots
                WHERE id = ?
                """,
                (payload.slot_id,),
            ).fetchone()
            if slot is None:
                raise VisitCompletionError(
                    "slot_not_found", "预约时段不存在"
                )
            if slot["status"] != "available":
                raise VisitCompletionError(
                    "slot_unavailable", "该时段已被预约或关闭"
                )
            connection.execute(
                """
                INSERT INTO appointments (
                    id, customer_id, slot_id, scheduled_at, service_item,
                    note, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'scheduled', ?, ?)
                """,
                (
                    appointment_id,
                    customer_id,
                    payload.slot_id,
                    slot["start_at"],
                    payload.service_item.strip(),
                    payload.note.strip(),
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE appointment_slots
                SET status = 'booked', updated_at = ?
                WHERE id = ? AND status = 'available'
                """,
                (now, payload.slot_id),
            )
        return self._get_appointment_sync(customer_id, appointment_id)

    def _update_appointment_status_sync(
        self,
        customer_id: str,
        appointment_id: str,
        status: str,
    ) -> AppointmentRecord:
        if status not in {"completed", "cancelled"}:
            raise VisitCompletionError(
                "invalid_appointment_status",
                "预约只能标记为已完成或已取消",
            )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT status, slot_id FROM appointments
                WHERE id = ? AND customer_id = ?
                """,
                (appointment_id, customer_id),
            ).fetchone()
            if row is None:
                raise VisitCompletionError(
                    "appointment_not_found", "预约记录不存在"
                )
            if row["status"] != "scheduled":
                raise VisitCompletionError(
                    "appointment_finished",
                    "该预约已经完成或取消，不能再次修改",
                )
            connection.execute(
                """
                UPDATE appointments
                SET status = ?, updated_at = ?
                WHERE id = ? AND customer_id = ?
                """,
                (status, self._now(), appointment_id, customer_id),
            )
            if row["slot_id"]:
                slot_status = "available" if status == "cancelled" else "completed"
                connection.execute(
                    """
                    UPDATE appointment_slots
                    SET status = ?, updated_at = ?
                    WHERE id = ? AND status = 'booked'
                    """,
                    (slot_status, self._now(), row["slot_id"]),
                )
        return self._get_appointment_sync(customer_id, appointment_id)

    def _get_slot_sync(self, slot_id: str) -> AppointmentSlotRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT s.id, s.schedule_date, s.start_at, s.end_at, s.status,
                       a.id AS appointment_id, a.customer_id,
                       c.name AS customer_name, a.service_item, a.note
                FROM appointment_slots s
                LEFT JOIN appointments a
                    ON a.slot_id = s.id
                   AND a.status IN ('scheduled', 'completed')
                LEFT JOIN customers c ON c.id = a.customer_id
                WHERE s.id = ?
                """,
                (slot_id,),
            ).fetchone()
        if row is None:
            raise VisitCompletionError(
                "slot_not_found", "预约时段不存在"
            )
        return self._slot_from_row(row)

    @staticmethod
    def _slot_from_row(row: sqlite3.Row) -> AppointmentSlotRecord:
        return AppointmentSlotRecord(
            id=row["id"],
            schedule_date=date.fromisoformat(row["schedule_date"]),
            start_at=datetime.fromisoformat(row["start_at"]),
            end_at=datetime.fromisoformat(row["end_at"]),
            status=row["status"],
            appointment_id=row["appointment_id"],
            customer_id=row["customer_id"],
            customer_name=row["customer_name"],
            service_item=row["service_item"] or "",
            note=row["note"] or "",
        )

    def _get_today_dashboard_sync(
        self,
        target_date: date,
        low_session_threshold: int,
        risk_days: int,
    ) -> TodayDashboard:
        target_iso = target_date.isoformat()
        customers = self._list_customers_sync("")
        customer_map = {customer.id: customer for customer in customers}

        with self._connect() as connection:
            investigation_rows = connection.execute(
                f"""
                SELECT {_INVESTIGATION_COLUMNS}
                FROM investigations
                ORDER BY visit_date DESC, created_at DESC
                """
            ).fetchall()
            appointment_rows = connection.execute(
                """
                SELECT id, customer_id, scheduled_at, service_item, note,
                       status, created_at, updated_at
                FROM appointments
                WHERE status = 'scheduled' AND substr(scheduled_at, 1, 10) = ?
                ORDER BY scheduled_at ASC
                """,
                (target_iso,),
            ).fetchall()
            followup_rows = connection.execute(
                """
                SELECT id, customer_id, investigation_id, due_date, note,
                       status, created_at, completed_at
                FROM followup_tasks
                WHERE status = 'pending' AND due_date <= ?
                ORDER BY due_date ASC, created_at ASC
                """,
                (target_iso,),
            ).fetchall()

        records = [self._investigation_from_row(row) for row in investigation_rows]
        latest_by_customer: dict[str, InvestigationRecord] = {}
        for record in records:
            latest_by_customer.setdefault(record.customer_id, record)

        appointments: list[WorkbenchCustomer] = []
        for row in appointment_rows:
            customer = customer_map.get(row["customer_id"])
            if customer is None:
                continue
            appointments.append(
                self._workbench_customer(
                    customer,
                    latest_by_customer.get(customer.id),
                    scheduled_at=datetime.fromisoformat(row["scheduled_at"]),
                    appointment_service=row["service_item"] or "未指定项目",
                )
            )

        due_followups: list[WorkbenchCustomer] = []
        for row in followup_rows:
            customer = customer_map.get(row["customer_id"])
            if customer is None:
                continue
            due_followups.append(
                self._workbench_customer(
                    customer,
                    latest_by_customer.get(customer.id),
                    followup_due_date=date.fromisoformat(row["due_date"]),
                    followup_note=row["note"],
                )
            )

        low_session_customers = [
            self._workbench_customer(
                customer, latest_by_customer.get(customer.id)
            )
            for customer in sorted(
                customers,
                key=lambda item: item.remaining_sessions,
            )
            if customer.selected_course
            and customer.remaining_sessions <= low_session_threshold
        ]

        risk_cutoff = target_date - timedelta(days=risk_days)
        risk_customers: list[WorkbenchCustomer] = []
        seen_risk_customers: set[str] = set()
        for record in records:
            if record.visit_date < risk_cutoff:
                continue
            customer = customer_map.get(record.customer_id)
            if customer is None or customer.id in seen_risk_customers:
                continue
            risk_label = self._risk_label(record.risk_assessment)
            if risk_label is None:
                continue
            seen_risk_customers.add(customer.id)
            item = self._workbench_customer(customer, record)
            item.risk_label = risk_label
            risk_customers.append(item)

        recent_visits: list[WorkbenchCustomer] = []
        customer_ids_by_latest = sorted(
            latest_by_customer,
            key=lambda customer_id: (
                latest_by_customer[customer_id].visit_date,
                latest_by_customer[customer_id].created_at,
            ),
            reverse=True,
        )
        for customer_id in customer_ids_by_latest[:8]:
            customer = customer_map.get(customer_id)
            if customer:
                recent_visits.append(
                    self._workbench_customer(
                        customer, latest_by_customer[customer_id]
                    )
                )

        return TodayDashboard(
            as_of=target_date,
            appointment_count=len(appointments),
            followup_count=len(due_followups),
            low_session_count=len(low_session_customers),
            risk_customer_count=len(risk_customers),
            today_appointments=appointments,
            due_followups=due_followups,
            low_session_customers=low_session_customers,
            risk_customers=risk_customers,
            recent_visits=recent_visits,
        )

    def _get_customer_script_sync(
        self, customer_id: str
    ) -> CustomerMessageDraft:
        customer = self._get_customer_sync(customer_id)
        records = self._list_investigations_sync(customer_id)
        quick = self._build_quick_summary(customer, records)
        complaint = quick.last_chief_complaint or "近期身体不适"
        danger = (
            f"如果出现{quick.recent_danger_signal}等情况，请及时到正规医院检查。"
            if quick.recent_danger_signal
            else "如果出现夜间痛醒、持续麻木无力、大小便异常等情况，请及时到正规医院检查。"
        )
        content = (
            f"{customer.name}您好，这次您主要反馈的是“{complaint}”。"
            "我们会根据本次现场核验后的实际情况进行温和的养护舒缓，"
            "具体感受会因个人情况而不同，不做疗效承诺。"
            "回家后请注意保暖，避免久坐久站和不当负重，并按现场告知的方式养护。"
            f"{danger}"
            "以上仅养护参考，不做医疗诊断，建议必要时前往医院检查；"
            "门店养护不能替代医院检查与医生意见。"
        )
        return CustomerMessageDraft(
            title=f"{customer.name} 顾客版沟通话术",
            content=content,
        )

    def _get_customer_handout_sync(
        self, customer_id: str
    ) -> CustomerMessageDraft:
        customer = self._get_customer_sync(customer_id)
        with self._connect() as connection:
            override = connection.execute(
                """
                SELECT title, content FROM customer_handouts
                WHERE customer_id = ?
                """,
                (customer_id,),
            ).fetchone()
        if override is not None:
            return CustomerMessageDraft(
                title=override["title"],
                content=override["content"],
                is_customized=True,
            )
        records = self._list_investigations_sync(customer_id)
        quick = self._build_quick_summary(customer, records)
        latest = records[0] if records else None
        followups = self._list_followups_sync(customer_id)
        next_followup = next(
            (task for task in followups if task.status == "pending"),
            None,
        )
        plan = (
            latest.care_plan.strip()
            if latest and latest.care_plan.strip()
            else "请遵照理疗师现场告知的养护方式执行。"
        )
        danger = (
            quick.recent_danger_signal
            or "夜间痛醒、持续麻木无力、大小便异常、持续眩晕、胸闷心慌"
        )
        followup_text = (
            next_followup.due_date.isoformat()
            if next_followup
            else "请按门店现场约定安排"
        )
        lines = [
            f"【{customer.name} 的居家养护提示】",
            "",
            f"记录日期：{datetime.now().astimezone().date().isoformat()}",
            f"本次主要反馈：{quick.last_chief_complaint or '暂无接诊记录'}",
            f"现场养护建议：{plan}",
            "",
            "居家注意事项：",
            "1. 注意保暖，避免患处直吹冷风。",
            "2. 避免长时间久坐、久站和突然负重。",
            "3. 不自行扳动关节或进行暴力拉伸。",
            "4. 活动以舒适、无疼痛加重为原则。",
            "",
            f"复诊安排：{followup_text}",
            f"危险预警：出现{danger}等情况，请及时到正规医院检查。",
            "",
            "免责：本提示仅作理疗养护参考，不构成医疗诊断，"
            "不能替代医院检查与医生诊疗。",
        ]
        return CustomerMessageDraft(
            title=f"{customer.name} 居家养护说明",
            content="\n".join(lines),
        )

    def _save_customer_handout_sync(
        self, customer_id: str, payload: CustomerHandoutUpdate
    ) -> CustomerMessageDraft:
        customer = self._get_customer_sync(customer_id)
        title = payload.title.strip()
        content = payload.content.strip()
        if not title or not content:
            raise VisitCompletionError(
                "invalid_handout", "养护说明标题和正文不能为空"
            )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO customer_handouts (
                    customer_id, title, content, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(customer_id) DO UPDATE SET
                    title = excluded.title,
                    content = excluded.content,
                    updated_at = excluded.updated_at
                """,
                (
                    customer_id,
                    title,
                    content,
                    self._now(),
                ),
            )
        return CustomerMessageDraft(
            title=title,
            content=content,
            is_customized=True,
        )

    def _reset_customer_handout_sync(
        self, customer_id: str
    ) -> CustomerMessageDraft:
        self._get_customer_sync(customer_id)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM customer_handouts WHERE customer_id = ?",
                (customer_id,),
            )
        return self._get_customer_handout_sync(customer_id)

    @staticmethod
    def _last_visit_summary(
        record: InvestigationRecord | None,
    ) -> LastVisitSummary | None:
        if record is None:
            return None
        return LastVisitSummary(
            investigation_id=record.id,
            visit_date=record.visit_date,
            visit_type=record.visit_type,
            chief_complaint=record.chief_complaint,
            risk_assessment=record.risk_assessment,
            care_plan=record.care_plan,
            followup_notes=record.followup_notes,
            sessions_used=record.sessions_used,
        )

    @classmethod
    def _workbench_customer(
        cls,
        customer: CustomerProfile,
        last_visit: InvestigationRecord | None,
        *,
        scheduled_at: datetime | None = None,
        appointment_service: str | None = None,
        followup_due_date: date | None = None,
        followup_note: str | None = None,
    ) -> WorkbenchCustomer:
        return WorkbenchCustomer(
            customer_id=customer.id,
            name=customer.name,
            phone=customer.phone,
            age=customer.age,
            health_issues=customer.health_issues,
            selected_course=customer.selected_course,
            remaining_sessions=customer.remaining_sessions,
            last_visit=cls._last_visit_summary(last_visit),
            scheduled_at=scheduled_at,
            appointment_service=appointment_service,
            followup_due_date=followup_due_date,
            followup_note=followup_note,
        )

    @staticmethod
    def _risk_label(risk_assessment: str) -> str | None:
        text = risk_assessment.strip()
        if not text:
            return None
        if "绝对禁忌" in text or "高风险" in text:
            return "高风险"
        if (
            "相对禁忌" in text
            or "建议医院" in text
            or "禁用" in text
        ):
            return "谨慎评估"
        if "适合常规" not in text:
            return "需复核"
        return None

    @classmethod
    def _build_quick_summary(
        cls,
        customer: CustomerProfile,
        records: list[InvestigationRecord],
    ) -> CustomerQuickSummary:
        latest = records[0] if records else None
        risk_record = next(
            (
                record
                for record in records
                if record.risk_assessment.strip()
            ),
            None,
        )
        risk_text = (
            risk_record.risk_assessment.strip()
            if risk_record
            else "未见明确风险记录"
        )
        risk_label = cls._risk_label(risk_text)
        risk_level = {
            "高风险": "high",
            "谨慎评估": "caution",
        }.get(risk_label or "", "none")
        followup_feedback = next(
            (
                record.followup_notes.strip()
                for record in records
                if record.followup_notes.strip()
            ),
            "",
        )
        danger_signal, danger_date = cls._find_recent_danger(records)
        return CustomerQuickSummary(
            health_issues=customer.health_issues,
            historical_cases=customer.historical_cases,
            major_risk=risk_text,
            major_risk_level=risk_level,
            selected_course=customer.selected_course,
            remaining_sessions=customer.remaining_sessions,
            latest_visit_date=latest.visit_date if latest else None,
            last_chief_complaint=latest.chief_complaint if latest else "",
            last_followup_feedback=followup_feedback,
            recent_danger_signal=danger_signal,
            danger_signal_date=danger_date,
        )

    @classmethod
    def _find_recent_danger(
        cls, records: list[InvestigationRecord]
    ) -> tuple[str, date | None]:
        patterns = (
            ("夜间痛/痛醒", r"夜间.{0,8}痛|痛.{0,8}夜间|痛醒"),
            ("静息痛", r"静息.{0,8}痛"),
            (
                "持续放射/麻木",
                r"(?:持续|一直|进行性).{0,8}(?:麻木|放射)"
                r"|(?:放射|串麻).{0,8}(?:麻木|痛|不适)",
            ),
            (
                "进行性无力",
                r"(?:进行性|越来越).{0,8}(?:无力|发软)"
                r"|(?:无力|发软).{0,8}(?:加重|持续)",
            ),
            (
                "大小便异常",
                r"大小便.{0,8}(?:异常|失禁|困难)|尿失禁|排便失禁",
            ),
            ("眩晕/剧烈头痛", r"持续眩晕|剧烈头痛"),
            ("胸闷/心慌", r"胸闷|心慌|胸痛"),
            ("不明原因消瘦", r"不明原因.{0,8}(?:消瘦|体重下降)"),
        )
        negations = re.compile(r"无|没有|否认|未见|不伴|并未")
        for record in records[:10]:
            text = "；".join(
                value
                for value in (
                    record.chief_complaint,
                    record.current_history,
                    record.objective_findings,
                    record.followup_notes,
                )
                if value
            )
            labels: list[str] = []
            for label, pattern in patterns:
                for match in re.finditer(pattern, text):
                    prefix = text[max(0, match.start() - 8) : match.start()]
                    if not negations.search(prefix) and label not in labels:
                        labels.append(label)
            if labels:
                return "、".join(labels[:3]), record.visit_date
            risk_level = cls._risk_label(record.risk_assessment)
            if risk_level in {"高风险", "谨慎评估"}:
                return record.risk_assessment.strip(), record.visit_date
        return "", None

    @staticmethod
    def _normalize_local_datetime(value: datetime) -> str:
        if value.tzinfo is None:
            local_timezone = datetime.now().astimezone().tzinfo
            value = value.replace(tzinfo=local_timezone)
        return value.astimezone().isoformat(timespec="minutes")

    @staticmethod
    def _appointment_from_row(row: sqlite3.Row) -> AppointmentRecord:
        return AppointmentRecord(
            id=row["id"],
            customer_id=row["customer_id"],
            slot_id=row["slot_id"],
            scheduled_at=datetime.fromisoformat(row["scheduled_at"]),
            service_item=row["service_item"],
            note=row["note"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _build_context_sync(
        self,
        customer_id: str,
        query: str,
        recent_limit: int,
        relevant_limit: int,
    ) -> CustomerMemoryContext:
        customer = self._get_customer_sync(customer_id)
        records = self._list_investigations_sync(customer_id)
        if not records:
            return CustomerMemoryContext(customer=customer, records=[])

        recent = records[:recent_limit]
        query_tokens = {
            token for token in tokenize(query) if len(token) > 1
        }
        scored: list[tuple[float, InvestigationRecord]] = []
        for record in records:
            blob = self._searchable_record(record)
            score = float(
                sum(min(blob.count(token), 3) for token in query_tokens)
            )
            for field in (
                record.chief_complaint,
                record.current_history,
                record.objective_findings,
                record.followup_notes,
            ):
                if field and field in query:
                    score += 4
            if score > 0:
                scored.append((score, record))
        scored.sort(key=lambda item: item[0], reverse=True)

        selected: list[InvestigationRecord] = []
        seen: set[str] = set()
        for record in [
            *(record for _, record in scored[:relevant_limit]),
            *recent,
        ]:
            if record.id not in seen:
                selected.append(record)
                seen.add(record.id)
        return CustomerMemoryContext(customer=customer, records=selected)

    def _count_customers_sync(self) -> int:
        with self._connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM customers"
            ).fetchone()[0]
        return int(count)

    @staticmethod
    def _searchable_record(record: InvestigationRecord) -> str:
        return " ".join(
            value
            for value in (
                record.chief_complaint,
                record.symptom_duration,
                record.trigger,
                record.current_history,
                record.medical_history,
                record.women_special,
                record.objective_findings,
                record.risk_assessment,
                record.care_plan,
                record.disclosure,
                record.followup_notes,
            )
            if value
        )

    @staticmethod
    def _customer_from_row(row: sqlite3.Row) -> CustomerProfile:
        return CustomerProfile(
            id=row["id"],
            name=row["name"],
            gender=row["gender"],
            age=row["age"],
            phone=row["phone"],
            occupation=row["occupation"],
            address=row["address"],
            health_issues=row["health_issues"],
            historical_cases=row["historical_cases"],
            selected_course=row["selected_course"],
            remaining_sessions=row["remaining_sessions"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _investigation_from_row(row: sqlite3.Row) -> InvestigationRecord:
        return InvestigationRecord(
            id=row["id"],
            customer_id=row["customer_id"],
            visit_date=date.fromisoformat(row["visit_date"]),
            visit_type=row["visit_type"],
            chief_complaint=row["chief_complaint"],
            symptom_duration=row["symptom_duration"],
            trigger=row["trigger"],
            current_history=row["current_history"],
            medical_history=row["medical_history"],
            women_special=row["women_special"],
            objective_findings=row["objective_findings"],
            risk_assessment=row["risk_assessment"],
            care_plan=row["care_plan"],
            disclosure=row["disclosure"],
            customer_signature=row["customer_signature"],
            therapist_signature=row["therapist_signature"],
            followup_notes=row["followup_notes"],
            sessions_used=row["sessions_used"],
            followup_date=(
                date.fromisoformat(row["followup_date"])
                if row["followup_date"]
                else None
            ),
            followup_note=row["followup_note"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _followup_from_row(row: sqlite3.Row) -> FollowupTask:
        return FollowupTask(
            id=row["id"],
            customer_id=row["customer_id"],
            investigation_id=row["investigation_id"],
            due_date=date.fromisoformat(row["due_date"]),
            note=row["note"],
            status=row["status"],
            completion_type=row["completion_type"],
            resolution_note=row["resolution_note"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )
