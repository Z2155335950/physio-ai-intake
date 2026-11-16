from __future__ import annotations

import asyncio
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth.models import StaffAccountUpdate
from app.config import get_settings


class StaffAccountTests(unittest.TestCase):
    def test_admin_can_create_therapist_and_permissions_are_enforced(self) -> None:
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            app = create_app(
                replace(
                    settings,
                    customer_db_path=temp_path / "staff.sqlite3",
                    tool_audit_db_path=temp_path / "audit.sqlite3",
                    backup_dir=temp_path / "backups",
                    backup_auto_enabled=False,
                    staff_access_password="initial-admin-pass",
                    staff_admin_username="admin",
                )
            )
            with TestClient(app) as client:
                login = client.post(
                    "/api/staff/login",
                    json={
                        "username": "admin",
                        "password": "initial-admin-pass",
                    },
                )
                self.assertEqual(login.status_code, 200)
                session = client.get("/api/staff/session").json()
                self.assertEqual(session["username"], "admin")
                self.assertEqual(session["role"], "admin")

                created = client.post(
                    "/api/staff/accounts",
                    json={
                        "username": "therapist1",
                        "password": "therapist-pass",
                        "role": "therapist",
                    },
                )
                self.assertEqual(created.status_code, 201)
                therapist_id = created.json()["id"]
                accounts = client.get("/api/staff/accounts").json()
                self.assertEqual(len(accounts), 2)
                self.assertTrue(
                    any(
                        account["username"] == "admin"
                        and account["role"] == "admin"
                        for account in accounts
                    )
                )

                client.post("/api/staff/logout")
                self.assertEqual(client.get("/api/customers").status_code, 401)
                therapist_login = client.post(
                    "/api/staff/login",
                    json={
                        "username": "therapist1",
                        "password": "therapist-pass",
                    },
                )
                self.assertEqual(therapist_login.status_code, 200)
                self.assertEqual(client.get("/api/customers").status_code, 200)
                self.assertEqual(client.get("/api/backups").status_code, 403)
                self.assertEqual(
                    client.get("/api/staff/accounts").status_code, 403
                )
                self.assertEqual(
                    client.get("/api/staff/login-attempts").status_code,
                    403,
                )

                asyncio.run(
                    app.state.auth_store.update_staff_account(
                        therapist_id,
                        StaffAccountUpdate(status="disabled"),
                    )
                )
                self.assertEqual(client.get("/api/customers").status_code, 401)
                admin_login = client.post(
                    "/api/staff/login",
                    json={
                        "username": "admin",
                        "password": "initial-admin-pass",
                    },
                )
                self.assertEqual(admin_login.status_code, 200)
                admin_id = next(
                    account["id"]
                    for account in accounts
                    if account["username"] == "admin"
                )
                last_admin = client.patch(
                    f"/api/staff/accounts/{admin_id}",
                    json={"status": "disabled"},
                )
                self.assertEqual(last_admin.status_code, 409)
                audit = client.get("/api/staff/audit?limit=100").json()
                self.assertTrue(
                    any(
                        entry["staff_username"] == "therapist1"
                        and entry["method"] == "GET"
                        and entry["path"] == "/api/customers"
                        for entry in audit
                    )
                )

    def test_local_bootstrap_admin_can_open_staff_management(self) -> None:
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            app = create_app(
                replace(
                    settings,
                    customer_db_path=temp_path / "local.sqlite3",
                    tool_audit_db_path=temp_path / "audit.sqlite3",
                    backup_dir=temp_path / "backups",
                    backup_auto_enabled=False,
                    staff_access_password="",
                )
            )
            with TestClient(app) as client:
                session = client.get("/api/staff/session").json()
                self.assertFalse(session["auth_required"])
                self.assertEqual(session["role"], "admin")
                created = client.post(
                    "/api/staff/accounts",
                    json={
                        "username": "first-admin",
                        "password": "first-admin-pass",
                        "role": "admin",
                    },
                )
                self.assertEqual(created.status_code, 201)
                login = client.post(
                    "/api/staff/login",
                    json={
                        "username": "first-admin",
                        "password": "first-admin-pass",
                    },
                )
                self.assertEqual(login.status_code, 200)

                audit = client.get("/api/staff/audit").json()
                self.assertTrue(
                    any(
                        entry["path"] == "/api/staff/accounts"
                        and entry["method"] == "POST"
                        for entry in audit
                    )
                )


if __name__ == "__main__":
    unittest.main()
