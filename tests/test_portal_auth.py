from __future__ import annotations

import asyncio
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth.models import PortalPrivacyPolicy
from app.auth.store import AuthError, PortalAuthStore
from app.config import get_settings
from app.memory.models import (
    CustomerCreate,
    InvestigationCreate,
    ScheduleWindow,
    SlotAppointmentCreate,
)
from app.memory.sqlite_store import SqliteCustomerMemoryStore


TEST_PRIVACY_POLICY = PortalPrivacyPolicy(
    version="test-policy-v1",
    purpose="用于测试顾客档案、预约、接诊和账号服务",
    retention="服务期间及最后一次联系后 3 年",
    deletion_rule="身份核验后删除线上资料，备份副本在 30 天内清理",
    contact="测试隐私负责人 13800000000",
)


class PortalAuthStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "portal.sqlite3"
        self.memory = SqliteCustomerMemoryStore(self.db_path)
        self.auth = PortalAuthStore(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_invite_registration_and_login(self) -> None:
        async def scenario():
            customer = await self.memory.create_customer(
                CustomerCreate(name="顾客甲", phone="13812345678")
            )
            invite = await self.auth.create_invite(customer.id)
            token = await self.auth.register(
                invite_code=invite.invite_code,
                phone_last4="5678",
                password="strong-pass-123",
                privacy_policy=TEST_PRIVACY_POLICY,
            )
            session = await self.auth.resolve_session(token, "customer")
            login_token = await self.auth.login_customer(
                "13812345678", "strong-pass-123"
            )
            login_session = await self.auth.resolve_session(
                login_token, "customer"
            )
            consent = await self.auth.get_latest_privacy_consent(
                session.account_id or ""
            )
            with self.assertRaises(AuthError):
                await self.auth.register(
                    invite_code=invite.invite_code,
                    phone_last4="5678",
                    password="strong-pass-123",
                    privacy_policy=TEST_PRIVACY_POLICY,
                )
            return customer, session, login_session, consent

        customer, session, login_session, consent = asyncio.run(scenario())
        self.assertEqual(session.customer_id, customer.id)
        self.assertEqual(login_session.customer_id, customer.id)
        self.assertIsNotNone(consent)
        self.assertEqual(consent.customer_id, customer.id)
        self.assertEqual(consent.policy_version, TEST_PRIVACY_POLICY.version)
        self.assertEqual(consent.contact, TEST_PRIVACY_POLICY.contact)

    def test_wrong_phone_last4_rejected(self) -> None:
        async def scenario():
            customer = await self.memory.create_customer(
                CustomerCreate(name="顾客乙", phone="13812340000")
            )
            invite = await self.auth.create_invite(customer.id)
            with self.assertRaises(AuthError) as raised:
                await self.auth.register(
                    invite_code=invite.invite_code,
                    phone_last4="9999",
                    password="strong-pass-123",
                    privacy_policy=TEST_PRIVACY_POLICY,
                )
            return raised.exception

        self.assertEqual(asyncio.run(scenario()).code, "phone_mismatch")


class PortalApiTests(unittest.TestCase):
    def test_customer_portal_is_read_only_and_scoped(self) -> None:
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            app = create_app(
                replace(
                    settings,
                    customer_db_path=temp_path / "portal-api.sqlite3",
                    tool_audit_db_path=temp_path / "audit.sqlite3",
                    backup_dir=temp_path / "backups",
                    backup_auto_enabled=False,
                    privacy_policy_version=TEST_PRIVACY_POLICY.version,
                    privacy_purpose=TEST_PRIVACY_POLICY.purpose,
                    privacy_retention=TEST_PRIVACY_POLICY.retention,
                    privacy_deletion_rule=TEST_PRIVACY_POLICY.deletion_rule,
                    privacy_contact=TEST_PRIVACY_POLICY.contact,
                    staff_access_password="",
                )
            )
            with TestClient(app) as client:
                policy = client.get("/api/portal/privacy-policy")
                self.assertEqual(policy.status_code, 200)
                self.assertTrue(policy.json()["registration_enabled"])
                self.assertEqual(
                    policy.json()["contact"], TEST_PRIVACY_POLICY.contact
                )
                self.assertEqual(
                    client.get("/api/portal/me").status_code, 401
                )
                customer = client.post(
                    "/api/customers",
                    json={"name": "顾客丙", "phone": "13900001234"},
                ).json()
                asyncio.run(
                    app.state.customer_memory.add_investigation(
                        customer["id"],
                        InvestigationCreate(
                            visit_date=date(2026, 11, 12),
                            chief_complaint="右侧腰部酸胀",
                            current_history="内部现病史不应返回",
                            risk_assessment="内部风险不应返回",
                            care_plan="注意保暖，避免久坐",
                        ),
                    )
                )
                client.post(
                    f"/api/customers/{customer['id']}/appointments",
                    json={
                        "scheduled_at": "2026-11-15T10:30",
                        "service_item": "腰部调理",
                    },
                )
                invite = client.post(
                    f"/api/customers/{customer['id']}/portal-invite"
                ).json()
                rejected = client.post(
                    "/api/portal/register",
                    json={
                        "invite_code": invite["invite_code"],
                        "phone_last4": "1234",
                        "password": "portal-pass-123",
                        "privacy_consent": False,
                    },
                )
                self.assertEqual(rejected.status_code, 400)
                registered = client.post(
                    "/api/portal/register",
                    json={
                        "invite_code": invite["invite_code"],
                        "phone_last4": "1234",
                        "password": "portal-pass-123",
                        "privacy_consent": True,
                    },
                )
                self.assertEqual(registered.status_code, 200)
                consent = client.get("/api/portal/privacy-consent")
                self.assertEqual(consent.status_code, 200)
                self.assertEqual(
                    consent.json()["policy_version"],
                    TEST_PRIVACY_POLICY.version,
                )
                self.assertEqual(
                    consent.json()["deletion_rule"],
                    TEST_PRIVACY_POLICY.deletion_rule,
                )
                portal = client.get("/api/portal/me")
                self.assertEqual(portal.status_code, 200)
                payload = portal.json()
                self.assertEqual(payload["customer_name"], "顾客丙")
                self.assertEqual(payload["remaining_sessions"], 0)
                self.assertEqual(len(payload["appointments"]), 1)
                self.assertEqual(len(payload["recent_visits"]), 1)
                self.assertNotIn(
                    "内部现病史不应返回", portal.text
                )
                self.assertNotIn("内部风险不应返回", portal.text)
                handout = client.get("/api/portal/handout")
                self.assertEqual(handout.status_code, 200)
                self.assertIn("居家养护说明", handout.json()["title"])

    def test_registration_is_disabled_without_privacy_contact(self) -> None:
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            app = create_app(
                replace(
                    settings,
                    customer_db_path=temp_path / "privacy-unconfigured.sqlite3",
                    tool_audit_db_path=temp_path / "audit.sqlite3",
                    backup_dir=temp_path / "backups",
                    backup_auto_enabled=False,
                    privacy_contact="",
                    staff_access_password="",
                )
            )
            with TestClient(app) as client:
                policy = client.get("/api/portal/privacy-policy")
                self.assertEqual(policy.status_code, 200)
                self.assertFalse(policy.json()["registration_enabled"])
                customer = client.post(
                    "/api/customers",
                    json={"name": "未配置隐私", "phone": "13700001234"},
                ).json()
                invite = client.post(
                    f"/api/customers/{customer['id']}/portal-invite"
                ).json()
                registered = client.post(
                    "/api/portal/register",
                    json={
                        "invite_code": invite["invite_code"],
                        "phone_last4": "1234",
                        "password": "portal-pass-123",
                        "privacy_consent": True,
                    },
                )
                self.assertEqual(registered.status_code, 503)

    def test_staff_password_protects_staff_api(self) -> None:
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            app = create_app(
                replace(
                    settings,
                    customer_db_path=temp_path / "staff-auth.sqlite3",
                    tool_audit_db_path=temp_path / "audit.sqlite3",
                    backup_dir=temp_path / "backups",
                    backup_auto_enabled=False,
                    privacy_contact=TEST_PRIVACY_POLICY.contact,
                    staff_access_password="staff-secret-123",
                )
            )
            with TestClient(app) as client:
                self.assertEqual(
                    client.get("/api/customers").status_code, 401
                )
                self.assertEqual(
                    client.get("/api/portal-admin/accounts").status_code,
                    401,
                )
                self.assertEqual(
                    client.post(
                        "/api/staff/login",
                        json={"username": "admin", "password": "wrong"},
                    ).status_code,
                    401,
                )
                login = client.post(
                    "/api/staff/login",
                    json={"username": "admin", "password": "staff-secret-123"},
                )
                self.assertEqual(login.status_code, 200)
                self.assertEqual(
                    client.get("/api/customers").status_code, 200
                )
                self.assertEqual(
                    client.get("/api/portal-admin/accounts").status_code,
                    200,
                )

    def test_customer_can_view_schedule_without_other_customer_names(self) -> None:
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            app = create_app(
                replace(
                    settings,
                    customer_db_path=temp_path / "portal-schedule.sqlite3",
                    tool_audit_db_path=temp_path / "audit.sqlite3",
                    backup_dir=temp_path / "backups",
                    backup_auto_enabled=False,
                    privacy_contact=TEST_PRIVACY_POLICY.contact,
                    staff_access_password="",
                )
            )
            with TestClient(app) as client:
                customer_a = client.post(
                    "/api/customers",
                    json={"name": "顾客甲", "phone": "13800001111"},
                ).json()
                customer_b = client.post(
                    "/api/customers",
                    json={"name": "顾客乙", "phone": "13800002222"},
                ).json()
                target = date(2026, 11, 20)
                schedule = asyncio.run(
                    app.state.customer_memory.configure_day_schedule(
                        ScheduleWindow(
                            schedule_date=target,
                            start_time="09:00",
                            end_time="11:00",
                            interval_minutes=60,
                        )
                    )
                )
                booked_slot = schedule.slots[0]
                asyncio.run(
                    app.state.customer_memory.schedule_customer_slot(
                        customer_a["id"],
                        SlotAppointmentCreate(slot_id=booked_slot.id),
                    )
                )
                invite_a = client.post(
                    f"/api/customers/{customer_a['id']}/portal-invite"
                ).json()
                client.post(
                    "/api/portal/register",
                    json={
                        "invite_code": invite_a["invite_code"],
                        "phone_last4": "1111",
                        "password": "customer-a-pass",
                        "privacy_consent": True,
                    },
                )
                own_schedule = client.get(
                    "/api/portal/schedule",
                    params={"schedule_date": target.isoformat()},
                )
                self.assertEqual(own_schedule.status_code, 200)
                own_booked = next(
                    slot
                    for slot in own_schedule.json()["slots"]
                    if slot["status"] == "booked"
                )
                self.assertTrue(own_booked["is_own"])

                client.post("/api/portal/logout")
                invite_b = client.post(
                    f"/api/customers/{customer_b['id']}/portal-invite"
                ).json()
                client.post(
                    "/api/portal/register",
                    json={
                        "invite_code": invite_b["invite_code"],
                        "phone_last4": "2222",
                        "password": "customer-b-pass",
                        "privacy_consent": True,
                    },
                )
                other_schedule = client.get(
                    "/api/portal/schedule",
                    params={"schedule_date": target.isoformat()},
                )
                self.assertEqual(other_schedule.status_code, 200)
                other_booked = next(
                    slot
                    for slot in other_schedule.json()["slots"]
                    if slot["status"] == "booked"
                )
                self.assertFalse(other_booked["is_own"])
                self.assertNotIn("顾客甲", other_schedule.text)

    def test_customer_password_recovery_and_data_deletion_flow(self) -> None:
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            app = create_app(
                replace(
                    settings,
                    customer_db_path=temp_path / "account-lifecycle.sqlite3",
                    tool_audit_db_path=temp_path / "audit.sqlite3",
                    backup_dir=temp_path / "backups",
                    backup_auto_enabled=False,
                    privacy_contact=TEST_PRIVACY_POLICY.contact,
                    staff_access_password="",
                )
            )
            with TestClient(app) as client:
                customer = client.post(
                    "/api/customers",
                    json={"name": "找回顾客", "phone": "13800008888"},
                ).json()
                asyncio.run(
                    app.state.customer_memory.add_investigation(
                        customer["id"],
                        InvestigationCreate(
                            visit_date=date(2026, 11, 12),
                            chief_complaint="腰部酸胀",
                            medical_history="高血压",
                        ),
                    )
                )
                invite = client.post(
                    f"/api/customers/{customer['id']}/portal-invite"
                ).json()
                self.assertEqual(
                    client.post(
                        "/api/portal/register",
                        json={
                            "invite_code": invite["invite_code"],
                            "phone_last4": "8888",
                            "password": "old-password-123",
                            "privacy_consent": True,
                        },
                    ).status_code,
                    200,
                )
                consent = client.get("/api/portal/privacy-consent")
                self.assertEqual(consent.status_code, 200)
                account_id = consent.json()["account_id"]
                self.assertEqual(
                    client.post(
                        "/api/portal/password/change",
                        json={
                            "current_password": "wrong-password",
                            "new_password": "new-password-123",
                        },
                    ).status_code,
                    400,
                )
                self.assertEqual(
                    client.post(
                        "/api/portal/password/change",
                        json={
                            "current_password": "old-password-123",
                            "new_password": "new-password-123",
                        },
                    ).status_code,
                    204,
                )
                self.assertEqual(client.get("/api/portal/me").status_code, 200)
                client.post("/api/portal/logout")
                self.assertEqual(
                    client.post(
                        "/api/portal/login",
                        json={
                            "phone": "13800008888",
                            "password": "old-password-123",
                        },
                    ).status_code,
                    401,
                )
                recovery = client.post(
                    f"/api/customers/{customer['id']}/portal-recovery-code"
                )
                self.assertEqual(recovery.status_code, 200)
                self.assertEqual(
                    client.post(
                        "/api/portal/password/reset",
                        json={
                            "phone": "13800008888",
                            "recovery_code": recovery.json()["recovery_code"],
                            "new_password": "reset-password-123",
                        },
                    ).status_code,
                    204,
                )
                self.assertEqual(
                    client.post(
                        "/api/portal/login",
                        json={
                            "phone": "13800008888",
                            "password": "reset-password-123",
                        },
                    ).status_code,
                    200,
                )
                deletion = client.post(
                    "/api/portal/data-deletion-requests",
                    json={
                        "current_password": "reset-password-123",
                        "reason": "不再使用网页账号",
                    },
                )
                self.assertEqual(deletion.status_code, 201)
                pending = client.get(
                    "/api/portal-admin/deletion-requests?status=pending"
                )
                self.assertEqual(pending.status_code, 200)
                self.assertEqual(len(pending.json()), 1)
                resolved = client.post(
                    f"/api/portal-admin/deletion-requests/{deletion.json()['id']}/resolve",
                    json={"action": "approve", "note": "本人身份已核验"},
                )
                self.assertEqual(resolved.status_code, 200)
                self.assertEqual(resolved.json()["status"], "approved")
                self.assertEqual(client.get("/api/portal/me").status_code, 401)

                erased = client.get(
                    f"/api/customers/{customer['id']}"
                ).json()
                self.assertTrue(
                    erased["customer"]["name"].startswith("已注销顾客-")
                )
                self.assertEqual(erased["customer"]["phone"], "")
                self.assertEqual(erased["investigations"], [])
                self.assertIsNone(
                    asyncio.run(
                        app.state.auth_store.get_latest_privacy_consent(
                            account_id
                        )
                    )
                )

    def test_customer_unbind_and_staff_revoke_close_access(self) -> None:
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            app = create_app(
                replace(
                    settings,
                    customer_db_path=temp_path / "account-access.sqlite3",
                    tool_audit_db_path=temp_path / "audit.sqlite3",
                    backup_dir=temp_path / "backups",
                    backup_auto_enabled=False,
                    privacy_contact=TEST_PRIVACY_POLICY.contact,
                    staff_access_password="",
                )
            )
            with TestClient(app) as client:
                customer_a = client.post(
                    "/api/customers",
                    json={"name": "解绑顾客", "phone": "13900001111"},
                ).json()
                invite_a = client.post(
                    f"/api/customers/{customer_a['id']}/portal-invite"
                ).json()
                client.post(
                    "/api/portal/register",
                    json={
                        "invite_code": invite_a["invite_code"],
                        "phone_last4": "1111",
                        "password": "unbind-pass-123",
                        "privacy_consent": True,
                    },
                )
                self.assertEqual(
                    client.post(
                        "/api/portal/unbind",
                        json={"current_password": "wrong-password"},
                    ).status_code,
                    400,
                )
                self.assertEqual(
                    client.post(
                        "/api/portal/unbind",
                        json={"current_password": "unbind-pass-123"},
                    ).status_code,
                    204,
                )
                self.assertEqual(client.get("/api/portal/me").status_code, 401)
                invite_again = client.post(
                    f"/api/customers/{customer_a['id']}/portal-invite"
                )
                self.assertEqual(invite_again.status_code, 200)

                customer_b = client.post(
                    "/api/customers",
                    json={"name": "撤销顾客", "phone": "13900002222"},
                ).json()
                invite_b = client.post(
                    f"/api/customers/{customer_b['id']}/portal-invite"
                ).json()
                client.post(
                    "/api/portal/register",
                    json={
                        "invite_code": invite_b["invite_code"],
                        "phone_last4": "2222",
                        "password": "revoke-pass-123",
                        "privacy_consent": True,
                    },
                )
                revoked = client.post(
                    f"/api/customers/{customer_b['id']}/portal-account/revoke"
                )
                self.assertEqual(revoked.status_code, 200)
                self.assertEqual(revoked.json()["status"], "revoked")
                self.assertEqual(client.get("/api/portal/me").status_code, 401)
                self.assertEqual(
                    client.post(
                        "/api/portal/login",
                        json={
                            "phone": "13900002222",
                            "password": "revoke-pass-123",
                        },
                    ).status_code,
                    401,
                )
                self.assertEqual(
                    client.post(
                        f"/api/customers/{customer_b['id']}/portal-invite"
                    ).status_code,
                    409,
                )
                restored = client.post(
                    f"/api/customers/{customer_b['id']}/portal-account/restore"
                )
                self.assertEqual(restored.status_code, 200)
                self.assertEqual(restored.json()["status"], "active")
                self.assertEqual(
                    client.post(
                        "/api/portal/login",
                        json={
                            "phone": "13900002222",
                            "password": "revoke-pass-123",
                        },
                    ).status_code,
                    200,
                )

    def test_login_throttling_records_failures_and_returns_retry(self) -> None:
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            app = create_app(
                replace(
                    settings,
                    customer_db_path=temp_path / "login-throttle.sqlite3",
                    tool_audit_db_path=temp_path / "audit.sqlite3",
                    backup_dir=temp_path / "backups",
                    backup_auto_enabled=False,
                    privacy_contact=TEST_PRIVACY_POLICY.contact,
                    staff_access_password="admin-throttle-pass",
                )
            )
            with TestClient(app) as client:
                first = client.post(
                    "/api/portal/login",
                    json={"phone": "19832126519", "password": "wrong-pass"},
                    headers={"X-Forwarded-For": "203.0.113.10"},
                )
                self.assertEqual(first.status_code, 401)
                second = client.post(
                    "/api/portal/login",
                    json={"phone": "19832126519", "password": "wrong-pass"},
                    headers={"X-Forwarded-For": "203.0.113.10"},
                )
                self.assertEqual(second.status_code, 429)
                self.assertGreaterEqual(
                    int(second.headers["Retry-After"]), 1
                )
                admin_login = client.post(
                    "/api/staff/login",
                    json={
                        "username": "admin",
                        "password": "admin-throttle-pass",
                    },
                )
                self.assertEqual(admin_login.status_code, 200)
                attempts = client.get(
                    "/api/staff/login-attempts?only_failures=true"
                )
                self.assertEqual(attempts.status_code, 200)
                self.assertEqual(len(attempts.json()), 2)
                self.assertEqual(attempts.json()[0]["role"], "customer")
                self.assertEqual(
                    attempts.json()[0]["ip_address"], "203.0.113.10"
                )
                self.assertEqual(
                    attempts.json()[0]["failure_reason"],
                    "invalid_credentials",
                )


class LoginThrottleStoreTests(unittest.TestCase):
    def test_account_and_ip_limits_are_enforced_independently(self) -> None:
        async def scenario():
            with tempfile.TemporaryDirectory() as temp_dir:
                store = PortalAuthStore(
                    Path(temp_dir) / "throttle-store.sqlite3"
                )
                with self.assertRaises(AuthError) as first:
                    await store.login_customer(
                        "19832126519", "wrong-pass", "203.0.113.20"
                    )
                self.assertEqual(first.exception.code, "invalid_credentials")
                with self.assertRaises(AuthError) as second:
                    await store.login_customer(
                        "19832126519", "wrong-pass", "203.0.113.20"
                    )
                self.assertEqual(second.exception.code, "login_throttled")
                self.assertGreaterEqual(
                    second.exception.retry_after_seconds, 1
                )

                account_block: AuthError | None = None
                for index in range(3, 9):
                    with self.assertRaises(AuthError) as raised:
                        await store.login_customer(
                            "19832126519",
                            "wrong-pass",
                            f"198.51.100.{index}",
                        )
                    account_block = raised.exception
                self.assertIsNotNone(account_block)
                self.assertGreaterEqual(
                    account_block.retry_after_seconds, 590
                )

                ip_block: AuthError | None = None
                for index in range(30):
                    with self.assertRaises(AuthError) as raised:
                        await store.login_customer(
                            f"1390000{index:04d}",
                            "wrong-pass",
                            "203.0.113.99",
                        )
                    ip_block = raised.exception
                self.assertIsNotNone(ip_block)
                self.assertGreaterEqual(
                    ip_block.retry_after_seconds, 890
                )

                attempts = await store.list_login_attempts(100, True)
                self.assertEqual(len(attempts), 38)
                self.assertTrue(
                    all(not attempt.success for attempt in attempts)
                )

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
