from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.auth.models import (
    AuthSession,
    LoginAttempt,
    PortalAccountSnapshot,
    PortalDeletionRequest,
    PortalInvite,
    PortalPrivacyConsent,
    PortalPrivacyPolicy,
    PortalRecoveryCode,
    StaffAccount,
    StaffAccountCreate,
    StaffAccountUpdate,
    StaffActionAudit,
)


class AuthError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        retry_after_seconds: int = 0,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retry_after_seconds = max(0, retry_after_seconds)


class PortalAuthStore:
    _THROTTLE_WINDOW_MINUTES = 15
    _ACCOUNT_FAILURE_LIMIT = 8
    _IP_FAILURE_LIMIT = 30
    _ACCOUNT_BLOCK_SECONDS = 10 * 60
    _IP_BLOCK_SECONDS = 15 * 60

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._initialize()
        self._staff_accounts_exist = self._has_staff_accounts_sync()

    @property
    def staff_login_required(self) -> bool:
        return self._staff_accounts_exist

    def bootstrap_staff_admin(
        self, username: str, password: str
    ) -> StaffAccount | None:
        if self._staff_accounts_exist or not password:
            return None
        account = self._create_staff_account_sync(
            StaffAccountCreate(
                username=username.strip() or "admin",
                password=password,
                role="admin",
            )
        )
        self._staff_accounts_exist = True
        return account

    async def create_invite(
        self, customer_id: str, *, expires_hours: int = 24
    ) -> PortalInvite:
        return await asyncio.to_thread(
            self._create_invite_sync, customer_id, expires_hours
        )

    async def register(
        self,
        *,
        invite_code: str,
        phone_last4: str,
        password: str,
        privacy_policy: PortalPrivacyPolicy,
    ) -> str:
        return await asyncio.to_thread(
            self._register_sync,
            invite_code,
            phone_last4,
            password,
            privacy_policy,
        )

    async def get_latest_privacy_consent(
        self, account_id: str
    ) -> PortalPrivacyConsent | None:
        return await asyncio.to_thread(
            self._get_latest_privacy_consent_sync, account_id
        )

    async def login_customer(
        self,
        phone: str,
        password: str,
        ip_address: str = "unknown",
    ) -> str:
        return await asyncio.to_thread(
            self._login_customer_sync, phone, password, ip_address
        )

    async def change_customer_password(
        self, account_id: str, current_password: str, new_password: str
    ) -> str:
        return await asyncio.to_thread(
            self._change_customer_password_sync,
            account_id,
            current_password,
            new_password,
        )

    async def create_customer_recovery_code(
        self, customer_id: str, *, expires_minutes: int = 30
    ) -> PortalRecoveryCode:
        return await asyncio.to_thread(
            self._create_customer_recovery_code_sync,
            customer_id,
            expires_minutes,
        )

    async def reset_customer_password(
        self, phone: str, recovery_code: str, new_password: str
    ) -> None:
        await asyncio.to_thread(
            self._reset_customer_password_sync,
            phone,
            recovery_code,
            new_password,
        )

    async def unbind_customer_account(
        self, account_id: str, current_password: str
    ) -> None:
        await asyncio.to_thread(
            self._unbind_customer_account_sync,
            account_id,
            current_password,
        )

    async def request_customer_data_deletion(
        self, account_id: str, current_password: str, reason: str
    ) -> PortalDeletionRequest:
        return await asyncio.to_thread(
            self._request_customer_data_deletion_sync,
            account_id,
            current_password,
            reason,
        )

    async def get_customer_account(
        self, customer_id: str
    ) -> PortalAccountSnapshot:
        return await asyncio.to_thread(
            self._get_customer_account_sync, customer_id
        )

    async def list_customer_accounts(
        self, query: str = ""
    ) -> list[PortalAccountSnapshot]:
        return await asyncio.to_thread(
            self._list_customer_accounts_sync, query
        )

    async def revoke_customer_account(
        self, customer_id: str
    ) -> PortalAccountSnapshot:
        return await asyncio.to_thread(
            self._revoke_customer_account_sync, customer_id
        )

    async def restore_customer_account(
        self, customer_id: str
    ) -> PortalAccountSnapshot:
        return await asyncio.to_thread(
            self._restore_customer_account_sync, customer_id
        )

    async def list_customer_deletion_requests(
        self, status: str = "pending"
    ) -> list[PortalDeletionRequest]:
        return await asyncio.to_thread(
            self._list_customer_deletion_requests_sync, status
        )

    async def resolve_customer_deletion_request(
        self,
        request_id: str,
        *,
        action: str,
        processed_by: str,
        note: str = "",
    ) -> PortalDeletionRequest:
        return await asyncio.to_thread(
            self._resolve_customer_deletion_request_sync,
            request_id,
            action,
            processed_by,
            note,
        )

    async def login_staff(
        self,
        username: str,
        password: str,
        ip_address: str = "unknown",
    ) -> str:
        return await asyncio.to_thread(
            self._login_staff_sync, username, password, ip_address
        )

    async def list_staff_accounts(self) -> list[StaffAccount]:
        return await asyncio.to_thread(self._list_staff_accounts_sync)

    async def create_staff_account(
        self, payload: StaffAccountCreate
    ) -> StaffAccount:
        return await asyncio.to_thread(
            self._create_staff_account_sync, payload
        )

    async def update_staff_account(
        self, account_id: str, payload: StaffAccountUpdate
    ) -> StaffAccount:
        return await asyncio.to_thread(
            self._update_staff_account_sync, account_id, payload
        )

    async def record_staff_action(
        self,
        *,
        staff_account_id: str | None,
        staff_username: str,
        staff_role: str,
        method: str,
        path: str,
        status_code: int,
    ) -> None:
        await asyncio.to_thread(
            self._record_staff_action_sync,
            staff_account_id,
            staff_username,
            staff_role,
            method,
            path,
            status_code,
        )

    async def list_staff_actions(
        self, limit: int = 100
    ) -> list[StaffActionAudit]:
        return await asyncio.to_thread(
            self._list_staff_actions_sync, limit
        )

    async def list_login_attempts(
        self, limit: int = 100, only_failures: bool = True
    ) -> list[LoginAttempt]:
        return await asyncio.to_thread(
            self._list_login_attempts_sync,
            limit,
            only_failures,
        )

    async def resolve_session(
        self, token: str, expected_role: str
    ) -> AuthSession | None:
        return await asyncio.to_thread(
            self._resolve_session_sync, token, expected_role
        )

    async def revoke_session(self, token: str) -> None:
        await asyncio.to_thread(self._revoke_session_sync, token)

    def _initialize(self) -> None:
        connection = sqlite3.connect(self._db_path)
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS portal_accounts (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL UNIQUE,
                    login_phone TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                );

                CREATE TABLE IF NOT EXISTS customer_invites (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    code_hash TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    used_at TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS auth_sessions (
                    token_hash TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    customer_id TEXT,
                    account_id TEXT,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS privacy_consents (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    customer_id TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    retention TEXT NOT NULL,
                    deletion_rule TEXT NOT NULL,
                    contact TEXT NOT NULL,
                    consented_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS staff_accounts (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'therapist',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_login_at TEXT
                );

                CREATE TABLE IF NOT EXISTS staff_action_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    staff_account_id TEXT,
                    staff_username TEXT NOT NULL,
                    staff_role TEXT NOT NULL,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS customer_recovery_codes (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    customer_id TEXT NOT NULL,
                    code_hash TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    used_at TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS portal_deletion_requests (
                    id TEXT PRIMARY KEY,
                    account_id TEXT,
                    customer_id TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    requested_at TEXT NOT NULL,
                    processed_at TEXT,
                    processed_by TEXT,
                    resolution_note TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    account_key TEXT NOT NULL,
                    account_display TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    failure_reason TEXT,
                    retry_after_seconds INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS login_throttle_state (
                    scope_type TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    first_failed_at TEXT NOT NULL,
                    last_failed_at TEXT NOT NULL,
                    blocked_until TEXT,
                    PRIMARY KEY (scope_type, scope_key)
                );

                CREATE INDEX IF NOT EXISTS idx_customer_invites_customer
                    ON customer_invites(customer_id, expires_at);
                CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry
                    ON auth_sessions(role, expires_at);
                CREATE INDEX IF NOT EXISTS idx_privacy_consents_account
                    ON privacy_consents(account_id, consented_at DESC);
                CREATE INDEX IF NOT EXISTS idx_staff_action_audit_time
                    ON staff_action_audit(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_customer_recovery_account
                    ON customer_recovery_codes(account_id, expires_at);
                CREATE INDEX IF NOT EXISTS idx_portal_deletion_status
                    ON portal_deletion_requests(status, requested_at DESC);
                CREATE INDEX IF NOT EXISTS idx_login_attempts_time
                    ON login_attempts(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_login_attempts_scope
                    ON login_attempts(role, account_key, created_at DESC);
                """
            )
            connection.commit()
        finally:
            connection.close()

    def _has_staff_accounts_sync(self) -> bool:
        connection = sqlite3.connect(self._db_path)
        try:
            count = connection.execute(
                "SELECT COUNT(*) FROM staff_accounts WHERE status = 'active'"
            ).fetchone()[0]
        finally:
            connection.close()
        return int(count) > 0

    def _create_staff_account_sync(
        self, payload: StaffAccountCreate
    ) -> StaffAccount:
        account_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        connection = sqlite3.connect(self._db_path)
        try:
            connection.execute(
                """
                INSERT INTO staff_accounts (
                    id, username, password_hash, role, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    account_id,
                    payload.username.strip(),
                    self._hash_password(payload.password),
                    payload.role,
                    now,
                    now,
                ),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise AuthError(
                "username_exists", "员工登录名已存在"
            ) from exc
        finally:
            connection.close()
        self._staff_accounts_exist = True
        return self._get_staff_account_sync(account_id)

    def _list_staff_accounts_sync(self) -> list[StaffAccount]:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT id, username, role, status, created_at, last_login_at
                FROM staff_accounts
                ORDER BY
                    CASE role WHEN 'admin' THEN 0 ELSE 1 END,
                    created_at ASC
                """
            ).fetchall()
        finally:
            connection.close()
        return [self._staff_account_from_row(row) for row in rows]

    def _get_staff_account_sync(self, account_id: str) -> StaffAccount:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                """
                SELECT id, username, role, status, created_at, last_login_at
                FROM staff_accounts WHERE id = ?
                """,
                (account_id,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise AuthError("staff_not_found", "员工账号不存在")
        return self._staff_account_from_row(row)

    def _update_staff_account_sync(
        self, account_id: str, payload: StaffAccountUpdate
    ) -> StaffAccount:
        current = self._get_staff_account_sync(account_id)
        target_role = payload.role or current.role
        target_status = payload.status or current.status
        if (
            current.role == "admin"
            and current.status == "active"
            and (target_role != "admin" or target_status != "active")
        ):
            connection = sqlite3.connect(self._db_path)
            try:
                active_admins = connection.execute(
                    """
                    SELECT COUNT(*) FROM staff_accounts
                    WHERE role = 'admin' AND status = 'active'
                    """
                ).fetchone()[0]
            finally:
                connection.close()
            if active_admins <= 1:
                raise AuthError(
                    "last_admin",
                    "不能停用或降级最后一个管理员账号",
                )

        updates: dict[str, object] = {
            "role": target_role,
            "status": target_status,
            "updated_at": datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            ),
        }
        if payload.new_password:
            updates["password_hash"] = self._hash_password(
                payload.new_password
            )
        assignments = ", ".join(f"{key} = ?" for key in updates)
        connection = sqlite3.connect(self._db_path)
        try:
            connection.execute(
                f"UPDATE staff_accounts SET {assignments} WHERE id = ?",
                (*updates.values(), account_id),
            )
            if target_status == "disabled":
                connection.execute(
                    """
                    DELETE FROM auth_sessions
                    WHERE role = 'staff' AND account_id = ?
                    """,
                    (account_id,),
                )
            connection.commit()
        finally:
            connection.close()
        self._staff_accounts_exist = self._has_staff_accounts_sync()
        return self._get_staff_account_sync(account_id)

    @staticmethod
    def _normalize_login_ip(ip_address: str) -> str:
        normalized = (ip_address or "").strip()
        return normalized[:128] if normalized else "unknown"

    def _normalize_login_account(
        self, role: str, value: str
    ) -> tuple[str, str]:
        if role == "customer":
            digits = "".join(char for char in value if char.isdigit())
            return digits or "unknown", self._masked_phone(digits)
        normalized = value.strip().casefold()
        return normalized or "unknown", value.strip() or "unknown"

    def _check_login_throttle_sync(
        self,
        *,
        role: str,
        account_key: str,
        account_display: str,
        ip_address: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=self._THROTTLE_WINDOW_MINUTES)
        pairs = (
            ("account", f"{role}:{account_key}", "login_account_blocked"),
            ("ip", f"{role}:{ip_address}", "login_ip_blocked"),
            (
                "pair",
                f"{role}:{account_key}:{ip_address}",
                "login_delay",
            ),
        )
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            for scope_type, scope_key, reason in pairs:
                row = connection.execute(
                    """
                    SELECT last_failed_at, blocked_until
                    FROM login_throttle_state
                    WHERE scope_type = ? AND scope_key = ?
                    """,
                    (scope_type, scope_key),
                ).fetchone()
                if row is None:
                    continue
                last_failed_at = datetime.fromisoformat(row["last_failed_at"])
                blocked_until = (
                    datetime.fromisoformat(row["blocked_until"])
                    if row["blocked_until"]
                    else None
                )
                if blocked_until and blocked_until > now:
                    retry_after = max(
                        1, int((blocked_until - now).total_seconds() + 0.999)
                    )
                    self._record_login_attempt_sync(
                        role=role,
                        account_key=account_key,
                        account_display=account_display,
                        ip_address=ip_address,
                        success=False,
                        failure_reason=reason,
                        retry_after_seconds=retry_after,
                        created_at=now,
                    )
                    raise AuthError(
                        reason,
                        self._login_retry_message(retry_after),
                        retry_after,
                    )
                if last_failed_at < cutoff and (
                    blocked_until is None or blocked_until < now
                ):
                    connection.execute(
                        """
                        DELETE FROM login_throttle_state
                        WHERE scope_type = ? AND scope_key = ?
                        """,
                        (scope_type, scope_key),
                    )
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _login_retry_message(retry_after_seconds: int) -> str:
        if retry_after_seconds >= 60:
            minutes = max(1, int(retry_after_seconds / 60))
            return f"登录尝试过于频繁，请约 {minutes} 分钟后再试"
        return f"登录尝试过于频繁，请 {retry_after_seconds} 秒后再试"

    def _record_login_attempt_sync(
        self,
        *,
        role: str,
        account_key: str,
        account_display: str,
        ip_address: str,
        success: bool,
        failure_reason: str | None,
        retry_after_seconds: int,
        created_at: datetime | None = None,
    ) -> None:
        connection = sqlite3.connect(self._db_path)
        try:
            connection.execute(
                """
                INSERT INTO login_attempts (
                    role, account_key, account_display, ip_address,
                    success, failure_reason, retry_after_seconds, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    role,
                    account_key,
                    account_display,
                    ip_address,
                    int(success),
                    failure_reason,
                    max(0, retry_after_seconds),
                    (created_at or datetime.now(timezone.utc)).isoformat(
                        timespec="seconds"
                    ),
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def _increment_login_throttle(
        self,
        connection: sqlite3.Connection,
        *,
        scope_type: str,
        scope_key: str,
        now: datetime,
        cutoff: datetime,
    ) -> datetime | None:
        row = connection.execute(
            """
            SELECT failure_count, first_failed_at, last_failed_at
            FROM login_throttle_state
            WHERE scope_type = ? AND scope_key = ?
            """,
            (scope_type, scope_key),
        ).fetchone()
        failure_count = 1
        first_failed_at = now
        if row is not None:
            last_failed_at = datetime.fromisoformat(row["last_failed_at"])
            if last_failed_at >= cutoff:
                failure_count = int(row["failure_count"]) + 1
                first_failed_at = datetime.fromisoformat(
                    row["first_failed_at"]
                )

        blocked_until: datetime | None = None
        if scope_type == "account" and failure_count >= self._ACCOUNT_FAILURE_LIMIT:
            blocked_until = now + timedelta(seconds=self._ACCOUNT_BLOCK_SECONDS)
        elif scope_type == "ip" and failure_count >= self._IP_FAILURE_LIMIT:
            blocked_until = now + timedelta(seconds=self._IP_BLOCK_SECONDS)
        elif scope_type == "pair":
            delays = (0, 0, 2, 5, 10, 30, 60, 120)
            delay = delays[min(failure_count, len(delays) - 1)]
            if delay:
                blocked_until = now + timedelta(seconds=delay)

        connection.execute(
            """
            INSERT INTO login_throttle_state (
                scope_type, scope_key, failure_count, first_failed_at,
                last_failed_at, blocked_until
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(scope_type, scope_key) DO UPDATE SET
                failure_count = excluded.failure_count,
                first_failed_at = excluded.first_failed_at,
                last_failed_at = excluded.last_failed_at,
                blocked_until = excluded.blocked_until
            """,
            (
                scope_type,
                scope_key,
                failure_count,
                first_failed_at.isoformat(timespec="seconds"),
                now.isoformat(timespec="seconds"),
                (
                    blocked_until.isoformat(timespec="seconds")
                    if blocked_until
                    else None
                ),
            ),
        )
        return blocked_until

    def _record_login_failure_sync(
        self,
        *,
        role: str,
        account_key: str,
        account_display: str,
        ip_address: str,
    ) -> int:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=self._THROTTLE_WINDOW_MINUTES)
        connection = sqlite3.connect(self._db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            blocked_times = [
                self._increment_login_throttle(
                    connection,
                    scope_type=scope_type,
                    scope_key=scope_key,
                    now=now,
                    cutoff=cutoff,
                )
                for scope_type, scope_key in (
                    ("account", f"{role}:{account_key}"),
                    ("ip", f"{role}:{ip_address}"),
                    ("pair", f"{role}:{account_key}:{ip_address}"),
                )
            ]
            retry_after = max(
                (
                    max(1, int((blocked - now).total_seconds() + 0.999))
                    for blocked in blocked_times
                    if blocked is not None
                ),
                default=0,
            )
            connection.execute(
                """
                INSERT INTO login_attempts (
                    role, account_key, account_display, ip_address,
                    success, failure_reason, retry_after_seconds, created_at
                ) VALUES (?, ?, ?, ?, 0, 'invalid_credentials', ?, ?)
                """,
                (
                    role,
                    account_key,
                    account_display,
                    ip_address,
                    retry_after,
                    now.isoformat(timespec="seconds"),
                ),
            )
            connection.commit()
            return retry_after
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _record_login_success_sync(
        self,
        *,
        role: str,
        account_key: str,
        account_display: str,
        ip_address: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        connection = sqlite3.connect(self._db_path)
        try:
            connection.execute(
                """
                INSERT INTO login_attempts (
                    role, account_key, account_display, ip_address,
                    success, failure_reason, retry_after_seconds, created_at
                ) VALUES (?, ?, ?, ?, 1, NULL, 0, ?)
                """,
                (role, account_key, account_display, ip_address, now),
            )
            connection.execute(
                """
                DELETE FROM login_throttle_state
                WHERE (scope_type = 'account' AND scope_key = ?)
                   OR (scope_type = 'pair' AND scope_key = ?)
                """,
                (f"{role}:{account_key}", f"{role}:{account_key}:{ip_address}"),
            )
            connection.commit()
        finally:
            connection.close()

    def _list_login_attempts_sync(
        self, limit: int, only_failures: bool
    ) -> list[LoginAttempt]:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT id, role, account_display, ip_address, success,
                       failure_reason, retry_after_seconds, created_at
                FROM login_attempts
                WHERE ? = 0 OR success = 0
                ORDER BY id DESC LIMIT ?
                """,
                (int(only_failures), max(1, min(limit, 500))),
            ).fetchall()
        finally:
            connection.close()
        return [
            LoginAttempt(
                id=row["id"],
                role=row["role"],
                account_display=row["account_display"],
                ip_address=row["ip_address"],
                success=bool(row["success"]),
                failure_reason=row["failure_reason"],
                retry_after_seconds=row["retry_after_seconds"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def _login_staff_sync(
        self, username: str, password: str, ip_address: str
    ) -> str:
        account_key, account_display = self._normalize_login_account(
            "staff", username
        )
        ip_address = self._normalize_login_ip(ip_address)
        self._check_login_throttle_sync(
            role="staff",
            account_key=account_key,
            account_display=account_display,
            ip_address=ip_address,
        )
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            account = connection.execute(
                """
                SELECT id, username, password_hash, role, status
                FROM staff_accounts WHERE username = ?
                """,
                (username.strip(),),
            ).fetchone()
            if (
                account is None
                or account["status"] != "active"
                or not self._verify_password(
                    password, account["password_hash"]
                )
            ):
                retry_after = self._record_login_failure_sync(
                    role="staff",
                    account_key=account_key,
                    account_display=account_display,
                    ip_address=ip_address,
                )
                raise AuthError(
                    (
                        "login_throttled"
                        if retry_after
                        else "invalid_credentials"
                    ),
                    (
                        self._login_retry_message(retry_after)
                        if retry_after
                        else "员工账号或密码错误"
                    ),
                    retry_after,
                )
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            connection.execute(
                "UPDATE staff_accounts SET last_login_at = ? WHERE id = ?",
                (now, account["id"]),
            )
            connection.commit()
        finally:
            connection.close()
        self._record_login_success_sync(
            role="staff",
            account_key=account_key,
            account_display=account_display,
            ip_address=ip_address,
        )
        return self._new_session_token_sync(
            role="staff",
            customer_id=None,
            account_id=account["id"],
            expires_hours=12,
        )

    def _record_staff_action_sync(
        self,
        account_id: str | None,
        username: str,
        role: str,
        method: str,
        path: str,
        status_code: int,
    ) -> None:
        connection = sqlite3.connect(self._db_path)
        try:
            connection.execute(
                """
                INSERT INTO staff_action_audit (
                    staff_account_id, staff_username, staff_role,
                    method, path, status_code, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    username,
                    role,
                    method,
                    path,
                    status_code,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def _list_staff_actions_sync(self, limit: int) -> list[StaffActionAudit]:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT id, staff_account_id, staff_username, staff_role,
                       method, path, status_code, created_at
                FROM staff_action_audit
                ORDER BY id DESC LIMIT ?
                """,
                (max(1, min(limit, 500)),),
            ).fetchall()
        finally:
            connection.close()
        return [
            StaffActionAudit(
                id=row["id"],
                staff_account_id=row["staff_account_id"],
                staff_username=row["staff_username"],
                staff_role=row["staff_role"],
                method=row["method"],
                path=row["path"],
                status_code=row["status_code"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    @staticmethod
    def _staff_account_from_row(row: sqlite3.Row) -> StaffAccount:
        return StaffAccount(
            id=row["id"],
            username=row["username"],
            role=row["role"],
            status=row["status"],
            created_at=row["created_at"],
            last_login_at=row["last_login_at"],
        )

    def _create_invite_sync(
        self, customer_id: str, expires_hours: int
    ) -> PortalInvite:
        code = secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:10]
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=max(1, expires_hours))
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            customer = connection.execute(
                "SELECT id FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()
            if customer is None:
                raise AuthError("customer_not_found", "客户不存在")
            existing_account = connection.execute(
                "SELECT id, status FROM portal_accounts WHERE customer_id = ?",
                (customer_id,),
            ).fetchone()
            if (
                existing_account is not None
                and existing_account["status"] != "unbound"
            ):
                raise AuthError(
                    "portal_already_linked", "该客户已经绑定顾客网页账号"
                )
            pending_deletion = connection.execute(
                """
                SELECT id FROM portal_deletion_requests
                WHERE customer_id = ? AND status = 'pending'
                """,
                (customer_id,),
            ).fetchone()
            if pending_deletion is not None:
                raise AuthError(
                    "deletion_pending",
                    "该客户有资料删除申请待处理，暂不能重新绑定",
                )
            connection.execute(
                """
                DELETE FROM customer_invites
                WHERE customer_id = ? AND used_at IS NULL
                """,
                (customer_id,),
            )
            connection.execute(
                """
                INSERT INTO customer_invites (
                    id, customer_id, code_hash, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    customer_id,
                    self._token_hash(code.upper()),
                    expires_at.isoformat(timespec="seconds"),
                    now.isoformat(timespec="seconds"),
                ),
            )
            connection.commit()
        finally:
            connection.close()
        return PortalInvite(invite_code=code, expires_at=expires_at)

    def _register_sync(
        self,
        invite_code: str,
        phone_last4: str,
        password: str,
        privacy_policy: PortalPrivacyPolicy,
    ) -> str:
        code_hash = self._token_hash(invite_code.strip().upper())
        now = datetime.now(timezone.utc)
        connection = sqlite3.connect(self._db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            invite = connection.execute(
                """
                SELECT id, customer_id, expires_at, used_at
                FROM customer_invites
                WHERE code_hash = ?
                """,
                (code_hash,),
            ).fetchone()
            if invite is None or invite["used_at"]:
                raise AuthError("invalid_invite", "邀请码无效或已使用")
            if datetime.fromisoformat(invite["expires_at"]) < now:
                raise AuthError("expired_invite", "邀请码已过期")
            existing = connection.execute(
                "SELECT id, status FROM portal_accounts WHERE customer_id = ?",
                (invite["customer_id"],),
            ).fetchone()
            if existing is not None and existing["status"] != "unbound":
                raise AuthError(
                    "portal_already_linked", "该客户已经绑定账号"
                )
            pending_deletion = connection.execute(
                """
                SELECT id FROM portal_deletion_requests
                WHERE customer_id = ? AND status = 'pending'
                """,
                (invite["customer_id"],),
            ).fetchone()
            if pending_deletion is not None:
                raise AuthError(
                    "deletion_pending",
                    "该客户有资料删除申请待处理，暂不能注册",
                )
            customer = connection.execute(
                "SELECT phone FROM customers WHERE id = ?",
                (invite["customer_id"],),
            ).fetchone()
            if customer is None or not customer["phone"]:
                raise AuthError(
                    "phone_required", "客户档案缺少手机号，无法注册网页账号"
                )
            phone_digits = "".join(
                char for char in customer["phone"] if char.isdigit()
            )
            if not phone_digits.endswith(phone_last4):
                raise AuthError(
                    "phone_mismatch", "手机号后四位不匹配"
                )
            account_id = (
                existing["id"] if existing is not None else str(uuid.uuid4())
            )
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO portal_accounts (
                        id, customer_id, login_phone, password_hash,
                        status, created_at
                    ) VALUES (?, ?, ?, ?, 'active', ?)
                    """,
                    (
                        account_id,
                        invite["customer_id"],
                        phone_digits,
                        self._hash_password(password),
                        now.isoformat(timespec="seconds"),
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE portal_accounts
                    SET login_phone = ?, password_hash = ?, status = 'active',
                        created_at = ?, last_login_at = NULL
                    WHERE id = ?
                    """,
                    (
                        phone_digits,
                        self._hash_password(password),
                        now.isoformat(timespec="seconds"),
                        account_id,
                    ),
                )
            connection.execute(
                "UPDATE customer_invites SET used_at = ? WHERE id = ?",
                (now.isoformat(timespec="seconds"), invite["id"]),
            )
            connection.execute(
                """
                INSERT INTO privacy_consents (
                    id, account_id, customer_id, policy_version, purpose,
                    retention, deletion_rule, contact, consented_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    account_id,
                    invite["customer_id"],
                    privacy_policy.version,
                    privacy_policy.purpose,
                    privacy_policy.retention,
                    privacy_policy.deletion_rule,
                    privacy_policy.contact,
                    now.isoformat(timespec="seconds"),
                ),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise AuthError(
                "phone_already_registered",
                "该手机号已经注册顾客账号，请直接登录",
            ) from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        token = self._new_session_token_sync(
            role="customer",
            customer_id=invite["customer_id"],
            account_id=account_id,
            expires_hours=24 * 30,
        )
        return token

    def _get_latest_privacy_consent_sync(
        self, account_id: str
    ) -> PortalPrivacyConsent | None:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                """
                SELECT id, account_id, customer_id, policy_version, purpose,
                       retention, deletion_rule, contact, consented_at
                FROM privacy_consents
                WHERE account_id = ?
                ORDER BY consented_at DESC, rowid DESC
                LIMIT 1
                """,
                (account_id,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        return PortalPrivacyConsent(**dict(row))

    def _login_customer_sync(
        self, phone: str, password: str, ip_address: str
    ) -> str:
        account_key, account_display = self._normalize_login_account(
            "customer", phone
        )
        ip_address = self._normalize_login_ip(ip_address)
        self._check_login_throttle_sync(
            role="customer",
            account_key=account_key,
            account_display=account_display,
            ip_address=ip_address,
        )
        phone_digits = account_key
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            account = connection.execute(
                """
                SELECT id, customer_id, password_hash, status
                FROM portal_accounts
                WHERE login_phone = ?
                """,
                (phone_digits,),
            ).fetchone()
            if (
                account is None
                or account["status"] != "active"
                or not self._verify_password(
                    password, account["password_hash"]
                )
            ):
                retry_after = self._record_login_failure_sync(
                    role="customer",
                    account_key=account_key,
                    account_display=account_display,
                    ip_address=ip_address,
                )
                raise AuthError(
                    (
                        "login_throttled"
                        if retry_after
                        else "invalid_credentials"
                    ),
                    (
                        self._login_retry_message(retry_after)
                        if retry_after
                        else "手机号或密码错误"
                    ),
                    retry_after,
                )
            connection.execute(
                "UPDATE portal_accounts SET last_login_at = ? WHERE id = ?",
                (
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    account["id"],
                ),
            )
            connection.commit()
        finally:
            connection.close()
        self._record_login_success_sync(
            role="customer",
            account_key=account_key,
            account_display=account_display,
            ip_address=ip_address,
        )
        return self._new_session_token_sync(
            role="customer",
            customer_id=account["customer_id"],
            account_id=account["id"],
            expires_hours=24 * 30,
        )

    def _change_customer_password_sync(
        self, account_id: str, current_password: str, new_password: str
    ) -> str:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            account = connection.execute(
                """
                SELECT id, customer_id, password_hash, status
                FROM portal_accounts WHERE id = ?
                """,
                (account_id,),
            ).fetchone()
            if (
                account is None
                or account["status"] != "active"
                or not self._verify_password(
                    current_password, account["password_hash"]
                )
            ):
                raise AuthError("invalid_current_password", "当前密码错误")
            connection.execute(
                "UPDATE portal_accounts SET password_hash = ? WHERE id = ?",
                (self._hash_password(new_password), account_id),
            )
            connection.execute(
                """
                UPDATE customer_recovery_codes
                SET used_at = ?
                WHERE account_id = ? AND used_at IS NULL
                """,
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), account_id),
            )
            connection.execute(
                """
                DELETE FROM auth_sessions
                WHERE role = 'customer' AND account_id = ?
                """,
                (account_id,),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return self._new_session_token_sync(
            role="customer",
            customer_id=account["customer_id"],
            account_id=account_id,
            expires_hours=24 * 30,
        )

    def _create_customer_recovery_code_sync(
        self, customer_id: str, expires_minutes: int
    ) -> PortalRecoveryCode:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        code = "".join(secrets.choice(alphabet) for _ in range(10))
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=max(5, min(expires_minutes, 120)))
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            account = connection.execute(
                """
                SELECT id, customer_id FROM portal_accounts
                WHERE customer_id = ? AND status = 'active'
                """,
                (customer_id,),
            ).fetchone()
            if account is None:
                raise AuthError(
                    "portal_account_not_active",
                    "该客户没有可找回的启用网页账号",
                )
            connection.execute(
                """
                UPDATE customer_recovery_codes SET used_at = ?
                WHERE account_id = ? AND used_at IS NULL
                """,
                (now.isoformat(timespec="seconds"), account["id"]),
            )
            connection.execute(
                """
                INSERT INTO customer_recovery_codes (
                    id, account_id, customer_id, code_hash,
                    expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    account["id"],
                    customer_id,
                    self._token_hash(code),
                    expires_at.isoformat(timespec="seconds"),
                    now.isoformat(timespec="seconds"),
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return PortalRecoveryCode(recovery_code=code, expires_at=expires_at)

    def _reset_customer_password_sync(
        self, phone: str, recovery_code: str, new_password: str
    ) -> None:
        phone_digits = "".join(char for char in phone if char.isdigit())
        now = datetime.now(timezone.utc)
        connection = sqlite3.connect(self._db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            account = connection.execute(
                """
                SELECT id, customer_id FROM portal_accounts
                WHERE login_phone = ? AND status = 'active'
                """,
                (phone_digits,),
            ).fetchone()
            if account is None:
                raise AuthError(
                    "invalid_recovery_code", "手机号或找回码无效"
                )
            recovery = connection.execute(
                """
                SELECT id, expires_at, used_at
                FROM customer_recovery_codes
                WHERE account_id = ? AND code_hash = ?
                """,
                (account["id"], self._token_hash(recovery_code.strip().upper())),
            ).fetchone()
            if recovery is None or recovery["used_at"]:
                raise AuthError(
                    "invalid_recovery_code", "手机号或找回码无效"
                )
            if datetime.fromisoformat(recovery["expires_at"]) < now:
                raise AuthError("expired_recovery_code", "找回码已过期")
            connection.execute(
                "UPDATE portal_accounts SET password_hash = ? WHERE id = ?",
                (self._hash_password(new_password), account["id"]),
            )
            connection.execute(
                "UPDATE customer_recovery_codes SET used_at = ? WHERE id = ?",
                (now.isoformat(timespec="seconds"), recovery["id"]),
            )
            connection.execute(
                """
                DELETE FROM auth_sessions
                WHERE role = 'customer' AND customer_id = ?
                """,
                (account["customer_id"],),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _unbind_customer_account_sync(
        self, account_id: str, current_password: str
    ) -> None:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            account = connection.execute(
                """
                SELECT id, customer_id, password_hash, status
                FROM portal_accounts WHERE id = ?
                """,
                (account_id,),
            ).fetchone()
            if (
                account is None
                or account["status"] != "active"
                or not self._verify_password(
                    current_password, account["password_hash"]
                )
            ):
                raise AuthError("invalid_current_password", "当前密码错误")
            connection.execute(
                """
                UPDATE portal_accounts
                SET status = 'unbound', last_login_at = NULL
                WHERE id = ?
                """,
                (account_id,),
            )
            connection.execute(
                """
                DELETE FROM auth_sessions
                WHERE role = 'customer' AND account_id = ?
                """,
                (account_id,),
            )
            connection.execute(
                """
                UPDATE customer_recovery_codes
                SET used_at = ?
                WHERE account_id = ? AND used_at IS NULL
                """,
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), account_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _request_customer_data_deletion_sync(
        self, account_id: str, current_password: str, reason: str
    ) -> PortalDeletionRequest:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        connection = sqlite3.connect(self._db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        request_id = ""
        try:
            connection.execute("BEGIN IMMEDIATE")
            account = connection.execute(
                """
                SELECT id, customer_id, password_hash, status
                FROM portal_accounts WHERE id = ?
                """,
                (account_id,),
            ).fetchone()
            if (
                account is None
                or account["status"] != "active"
                or not self._verify_password(
                    current_password, account["password_hash"]
                )
            ):
                raise AuthError("invalid_current_password", "当前密码错误")
            pending = connection.execute(
                """
                SELECT id FROM portal_deletion_requests
                WHERE customer_id = ? AND status = 'pending'
                ORDER BY requested_at DESC LIMIT 1
                """,
                (account["customer_id"],),
            ).fetchone()
            if pending is None:
                request_id = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO portal_deletion_requests (
                        id, account_id, customer_id, reason, status,
                        requested_at
                    ) VALUES (?, ?, ?, ?, 'pending', ?)
                    """,
                    (
                        request_id,
                        account_id,
                        account["customer_id"],
                        reason.strip(),
                        now,
                    ),
                )
            else:
                request_id = pending["id"]
                connection.execute(
                    """
                    UPDATE portal_deletion_requests
                    SET reason = ?, requested_at = ?, processed_at = NULL,
                        processed_by = NULL, resolution_note = ''
                    WHERE id = ?
                    """,
                    (reason.strip(), now, request_id),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        request = self._get_customer_deletion_request_sync(request_id)
        if request is None:
            raise AuthError("deletion_request_not_found", "删除申请提交失败")
        return request

    def _get_customer_account_sync(
        self, customer_id: str
    ) -> PortalAccountSnapshot:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                """
                SELECT c.id AS customer_id, c.name AS customer_name, c.phone,
                       pa.login_phone, pa.status AS account_status,
                       pa.created_at, pa.last_login_at,
                       (
                           SELECT id FROM portal_deletion_requests dr
                           WHERE dr.customer_id = c.id AND dr.status = 'pending'
                           ORDER BY dr.requested_at DESC LIMIT 1
                       ) AS pending_deletion_request_id,
                       (
                           SELECT status FROM portal_deletion_requests dr
                           WHERE dr.customer_id = c.id
                           ORDER BY dr.requested_at DESC LIMIT 1
                       ) AS latest_deletion_request_status
                FROM customers c
                LEFT JOIN portal_accounts pa ON pa.customer_id = c.id
                WHERE c.id = ?
                """,
                (customer_id,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise AuthError("customer_not_found", "客户不存在")
        return self._account_snapshot_from_row(row)

    def _list_customer_accounts_sync(
        self, query: str
    ) -> list[PortalAccountSnapshot]:
        normalized = query.strip()
        pattern = f"%{normalized}%"
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT c.id AS customer_id, c.name AS customer_name, c.phone,
                       pa.login_phone, pa.status AS account_status,
                       pa.created_at, pa.last_login_at,
                       (
                           SELECT id FROM portal_deletion_requests dr
                           WHERE dr.customer_id = c.id AND dr.status = 'pending'
                           ORDER BY dr.requested_at DESC LIMIT 1
                       ) AS pending_deletion_request_id,
                       (
                           SELECT status FROM portal_deletion_requests dr
                           WHERE dr.customer_id = c.id
                           ORDER BY dr.requested_at DESC LIMIT 1
                       ) AS latest_deletion_request_status
                FROM customers c
                LEFT JOIN portal_accounts pa ON pa.customer_id = c.id
                WHERE ? = '' OR c.name LIKE ? OR c.phone LIKE ? OR pa.login_phone LIKE ?
                ORDER BY
                    CASE
                        WHEN pa.status = 'active' THEN 0
                        WHEN pa.status = 'revoked' THEN 1
                        WHEN pa.status = 'unbound' THEN 2
                        ELSE 3
                    END,
                    c.updated_at DESC
                LIMIT 300
                """,
                (normalized, pattern, pattern, pattern),
            ).fetchall()
        finally:
            connection.close()
        return [self._account_snapshot_from_row(row) for row in rows]

    def _revoke_customer_account_sync(
        self, customer_id: str
    ) -> PortalAccountSnapshot:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            account = connection.execute(
                """
                SELECT id, status FROM portal_accounts WHERE customer_id = ?
                """,
                (customer_id,),
            ).fetchone()
            if account is None:
                raise AuthError("portal_account_not_found", "该客户尚未绑定网页账号")
            connection.execute(
                """
                UPDATE portal_accounts
                SET status = 'revoked', last_login_at = NULL
                WHERE id = ?
                """,
                (account["id"],),
            )
            connection.execute(
                """
                DELETE FROM auth_sessions
                WHERE role = 'customer' AND customer_id = ?
                """,
                (customer_id,),
            )
            connection.execute(
                """
                UPDATE customer_recovery_codes
                SET used_at = ?
                WHERE customer_id = ? AND used_at IS NULL
                """,
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), customer_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return self._get_customer_account_sync(customer_id)

    def _restore_customer_account_sync(
        self, customer_id: str
    ) -> PortalAccountSnapshot:
        connection = sqlite3.connect(self._db_path)
        try:
            account = connection.execute(
                "SELECT id, status FROM portal_accounts WHERE customer_id = ?",
                (customer_id,),
            ).fetchone()
            if account is None:
                raise AuthError("portal_account_not_found", "该客户尚未绑定网页账号")
            if account[1] != "revoked":
                raise AuthError("portal_account_not_revoked", "该账号不是撤销状态")
            connection.execute(
                "UPDATE portal_accounts SET status = 'active' WHERE id = ?",
                (account[0],),
            )
            connection.commit()
        finally:
            connection.close()
        return self._get_customer_account_sync(customer_id)

    def _list_customer_deletion_requests_sync(
        self, status: str
    ) -> list[PortalDeletionRequest]:
        allowed = {
            "pending",
            "approved",
            "rejected",
            "cancelled",
        }
        selected_status = status if status in allowed else "pending"
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT dr.*, c.name AS customer_name,
                       COALESCE(pa.login_phone, '') AS login_phone
                FROM portal_deletion_requests dr
                LEFT JOIN customers c ON c.id = dr.customer_id
                LEFT JOIN portal_accounts pa ON pa.id = dr.account_id
                WHERE dr.status = ?
                ORDER BY dr.requested_at DESC
                LIMIT 300
                """,
                (selected_status,),
            ).fetchall()
        finally:
            connection.close()
        return [self._deletion_request_from_row(row) for row in rows]

    def _get_customer_deletion_request_sync(
        self, request_id: str
    ) -> PortalDeletionRequest | None:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                """
                SELECT dr.*, c.name AS customer_name,
                       COALESCE(pa.login_phone, '') AS login_phone
                FROM portal_deletion_requests dr
                LEFT JOIN customers c ON c.id = dr.customer_id
                LEFT JOIN portal_accounts pa ON pa.id = dr.account_id
                WHERE dr.id = ?
                """,
                (request_id,),
            ).fetchone()
        finally:
            connection.close()
        return self._deletion_request_from_row(row) if row else None

    def _resolve_customer_deletion_request_sync(
        self,
        request_id: str,
        action: str,
        processed_by: str,
        note: str,
    ) -> PortalDeletionRequest:
        if action not in {"approve", "reject"}:
            raise AuthError("invalid_action", "无效的处理方式")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        connection = sqlite3.connect(self._db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            request = connection.execute(
                """
                SELECT id, customer_id, status
                FROM portal_deletion_requests WHERE id = ?
                """,
                (request_id,),
            ).fetchone()
            if request is None:
                raise AuthError(
                    "deletion_request_not_found", "删除申请不存在"
                )
            if request["status"] != "pending":
                raise AuthError(
                    "deletion_request_processed", "该删除申请已经处理"
                )
            customer_id = request["customer_id"]
            if action == "reject":
                connection.execute(
                    """
                    UPDATE portal_deletion_requests
                    SET status = 'rejected', processed_at = ?,
                        processed_by = ?, resolution_note = ?
                    WHERE id = ?
                    """,
                    (now, processed_by, note.strip(), request_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE appointment_slots
                    SET status = 'available', updated_at = ?
                    WHERE status != 'completed' AND id IN (
                        SELECT slot_id FROM appointments
                        WHERE customer_id = ? AND slot_id IS NOT NULL
                    )
                    """,
                    (now, customer_id),
                )
                connection.execute(
                    "DELETE FROM followup_tasks WHERE customer_id = ?",
                    (customer_id,),
                )
                connection.execute(
                    "DELETE FROM visit_completion_challenges WHERE customer_id = ?",
                    (customer_id,),
                )
                connection.execute(
                    "DELETE FROM investigations WHERE customer_id = ?",
                    (customer_id,),
                )
                connection.execute(
                    "DELETE FROM appointments WHERE customer_id = ?",
                    (customer_id,),
                )
                connection.execute(
                    "DELETE FROM customer_handouts WHERE customer_id = ?",
                    (customer_id,),
                )
                has_pdf_intake = connection.execute(
                    """
                    SELECT 1 FROM sqlite_master
                    WHERE type = 'table' AND name = 'pdf_intake_drafts'
                    """
                ).fetchone()
                if has_pdf_intake:
                    connection.execute(
                        "DELETE FROM pdf_intake_drafts WHERE customer_id = ?",
                        (customer_id,),
                    )
                has_pdf_edits = connection.execute(
                    """
                    SELECT 1 FROM sqlite_master
                    WHERE type = 'table' AND name = 'pdf_intake_edit_records'
                    """
                ).fetchone()
                if has_pdf_edits:
                    connection.execute(
                        """
                        DELETE FROM pdf_intake_edit_records
                        WHERE customer_id = ?
                        """,
                        (customer_id,),
                    )
                connection.execute(
                    "DELETE FROM customer_invites WHERE customer_id = ?",
                    (customer_id,),
                )
                connection.execute(
                    "DELETE FROM customer_recovery_codes WHERE customer_id = ?",
                    (customer_id,),
                )
                connection.execute(
                    """
                    DELETE FROM auth_sessions
                    WHERE role = 'customer' AND customer_id = ?
                    """,
                    (customer_id,),
                )
                connection.execute(
                    "DELETE FROM privacy_consents WHERE customer_id = ?",
                    (customer_id,),
                )
                connection.execute(
                    "DELETE FROM portal_accounts WHERE customer_id = ?",
                    (customer_id,),
                )
                connection.execute(
                    """
                    UPDATE customers
                    SET name = ?, gender = '', age = '', phone = '',
                        occupation = '', address = '', health_issues = '',
                        historical_cases = '', selected_course = '',
                        remaining_sessions = 0, notes = '', updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        f"已注销顾客-{customer_id[:6]}",
                        now,
                        customer_id,
                    ),
                )
                connection.execute(
                    """
                    UPDATE portal_deletion_requests
                    SET reason = ''
                    WHERE customer_id = ?
                    """,
                    (customer_id,),
                )
                connection.execute(
                    """
                    UPDATE portal_deletion_requests
                    SET reason = '', status = 'approved', processed_at = ?,
                        processed_by = ?, resolution_note = ?
                    WHERE id = ?
                    """,
                    (now, processed_by, note.strip(), request_id),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        resolved = self._get_customer_deletion_request_sync(request_id)
        if resolved is None:
            raise AuthError("deletion_request_not_found", "删除申请不存在")
        return resolved

    @staticmethod
    def _masked_phone(value: str) -> str:
        digits = "".join(char for char in value if char.isdigit())
        return f"*******{digits[-4:]}" if len(digits) >= 4 else ""

    @classmethod
    def _account_snapshot_from_row(
        cls, row: sqlite3.Row
    ) -> PortalAccountSnapshot:
        account_status = row["account_status"]
        latest_status = row["latest_deletion_request_status"]
        if account_status == "active":
            status = "active"
        elif account_status == "revoked":
            status = "revoked"
        elif latest_status == "approved":
            status = "deleted"
        else:
            status = "unbound"
        return PortalAccountSnapshot(
            customer_id=row["customer_id"],
            customer_name=row["customer_name"],
            status=status,
            login_phone_masked=cls._masked_phone(row["login_phone"] or ""),
            created_at=row["created_at"],
            last_login_at=row["last_login_at"],
            pending_deletion_request_id=row["pending_deletion_request_id"],
            latest_deletion_request_status=latest_status,
        )

    @classmethod
    def _deletion_request_from_row(
        cls, row: sqlite3.Row
    ) -> PortalDeletionRequest:
        return PortalDeletionRequest(
            id=row["id"],
            customer_id=row["customer_id"],
            customer_name=row["customer_name"] or "已注销客户",
            login_phone_masked=cls._masked_phone(row["login_phone"] or ""),
            reason=row["reason"],
            status=row["status"],
            requested_at=row["requested_at"],
            processed_at=row["processed_at"],
            processed_by=row["processed_by"],
            resolution_note=row["resolution_note"],
        )

    async def _create_session(
        self,
        *,
        role: str,
        customer_id: str | None,
        account_id: str | None,
        expires_hours: int,
    ) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=expires_hours)
        return await asyncio.to_thread(
            self._create_session_sync,
            token,
            role,
            customer_id,
            account_id,
            now,
            expires_at,
        )

    def _create_session_sync(
        self,
        token: str,
        role: str,
        customer_id: str | None,
        account_id: str | None,
        now: datetime,
        expires_at: datetime,
    ) -> str:
        connection = sqlite3.connect(self._db_path)
        try:
            connection.execute(
                "DELETE FROM auth_sessions WHERE expires_at < ?",
                (now.isoformat(timespec="seconds"),),
            )
            connection.execute(
                """
                INSERT INTO auth_sessions (
                    token_hash, role, customer_id, account_id,
                    expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    self._token_hash(token),
                    role,
                    customer_id,
                    account_id,
                    expires_at.isoformat(timespec="seconds"),
                    now.isoformat(timespec="seconds"),
                ),
            )
            connection.commit()
        finally:
            connection.close()
        return token

    def _new_session_token_sync(
        self,
        *,
        role: str,
        customer_id: str | None,
        account_id: str | None,
        expires_hours: int,
    ) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=expires_hours)
        return self._create_session_sync(
            token,
            role,
            customer_id,
            account_id,
            now,
            expires_at,
        )

    def _resolve_session_sync(
        self, token: str, expected_role: str
    ) -> AuthSession | None:
        if not token:
            return None
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                """
                SELECT s.role, s.customer_id, s.account_id, s.expires_at,
                       sa.username AS staff_username,
                       sa.role AS staff_role,
                       sa.status AS staff_status,
                       pa.status AS portal_status
                FROM auth_sessions s
                LEFT JOIN staff_accounts sa ON sa.id = s.account_id
                LEFT JOIN portal_accounts pa ON pa.id = s.account_id
                WHERE s.token_hash = ? AND s.role = ?
                """,
                (self._token_hash(token), expected_role),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at < datetime.now(timezone.utc):
            return None
        if expected_role == "staff" and (
            not row["staff_username"] or row["staff_status"] != "active"
        ):
            return None
        if expected_role == "customer" and row["portal_status"] != "active":
            return None
        return AuthSession(
            role=row["role"],
            customer_id=row["customer_id"],
            account_id=row["account_id"],
            staff_username=row["staff_username"],
            staff_role=row["staff_role"],
            expires_at=expires_at,
        )

    def _revoke_session_sync(self, token: str) -> None:
        connection = sqlite3.connect(self._db_path)
        try:
            connection.execute(
                "DELETE FROM auth_sessions WHERE token_hash = ?",
                (self._token_hash(token),),
            )
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=32,
        )
        return (
            "scrypt$16384$8$1$"
            f"{base64.b64encode(salt).decode()}$"
            f"{base64.b64encode(digest).decode()}"
        )

    @classmethod
    def _verify_password(cls, password: str, encoded: str) -> bool:
        try:
            algorithm, n, r, p, salt, expected = encoded.split("$")
            if algorithm != "scrypt":
                return False
            digest = hashlib.scrypt(
                password.encode("utf-8"),
                salt=base64.b64decode(salt),
                n=int(n),
                r=int(r),
                p=int(p),
                dklen=32,
            )
            return hmac.compare_digest(
                digest, base64.b64decode(expected)
            )
        except (ValueError, TypeError):
            return False
