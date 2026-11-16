from __future__ import annotations

import asyncio
import os
import tempfile
import time
import unittest
import zipfile
from dataclasses import replace
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from app.backup.service import BackupError, BackupService
from app.config import get_settings
from app.memory.models import CustomerCreate
from app.memory.sqlite_store import SqliteCustomerMemoryStore
from app.tools.audit import SqliteToolAuditStore


class BackupServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.customer_db = self.root / "customer.sqlite3"
        self.audit_db = self.root / "audit.sqlite3"
        self.customer_store = SqliteCustomerMemoryStore(self.customer_db)
        SqliteToolAuditStore(self.audit_db)
        self.service = BackupService(
            customer_db_path=self.customer_db,
            audit_db_path=self.audit_db,
            backup_dir=self.root / "backups",
            automatic_password="auto-backup-pass-123",
            retention_days=2,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_customer(self, name: str):
        return asyncio.run(
            self.customer_store.create_customer(
                CustomerCreate(name=name, phone="13800000022")
            )
        )

    def test_new_backup_is_encrypted_and_restore_full_database(self) -> None:
        customer_a = self._create_customer("备份前客户")
        content, info = asyncio.run(self.service.export_bytes())
        self.assertTrue(info.encrypted)
        self.assertTrue(content.startswith(b"PHYSIOENC1"))
        self.assertTrue(info.filename.endswith(".enc"))

        self._create_customer("备份后客户")
        preview = asyncio.run(self.service.preview_restore(content))
        self.assertEqual(preview.customer_count, 1)
        self.assertIn("customer_memory.sqlite3", preview.database_files)
        result = asyncio.run(
            self.service.confirm_restore(preview.restore_id)
        )
        self.assertTrue(result.restored)
        customers = asyncio.run(self.customer_store.list_customers())
        self.assertEqual([customer.id for customer in customers], [customer_a.id])
        self.assertTrue(
            (self.root / "backups" / "rollback" / result.safety_backup).exists()
        )
        self.assertTrue(result.safety_backup.endswith(".enc"))

    def test_backup_creation_is_refused_without_encryption_password(self) -> None:
        service = BackupService(
            customer_db_path=self.customer_db,
            audit_db_path=self.audit_db,
            backup_dir=self.root / "unencrypted-refused",
        )
        with self.assertRaises(BackupError) as raised:
            asyncio.run(service.export_bytes())
        self.assertEqual(
            raised.exception.code, "encryption_password_required"
        )
        self.assertFalse(
            list((self.root / "unencrypted-refused").rglob("*.physio-backup"))
        )

    def test_legacy_plain_backup_remains_readable(self) -> None:
        self._create_customer("旧版备份客户")
        archive_bytes, _ = self.service._build_archive_bytes()
        preview = asyncio.run(
            self.service.preview_restore(archive_bytes)
        )
        self.assertFalse(preview.encrypted)
        self.assertEqual(preview.customer_count, 1)

    def test_encrypted_backup_requires_correct_password(self) -> None:
        self._create_customer("加密客户")
        content, info = asyncio.run(
            self.service.export_bytes(password="strong-pass-123")
        )
        self.assertTrue(info.encrypted)
        self.assertTrue(content.startswith(b"PHYSIOENC1"))
        with self.assertRaises(BackupError) as raised:
            asyncio.run(
                self.service.preview_restore(content, "wrong-password")
            )
        self.assertEqual(
            raised.exception.code, "invalid_backup_password"
        )
        preview = asyncio.run(
            self.service.preview_restore(content, "strong-pass-123")
        )
        self.assertTrue(preview.encrypted)
        self.assertEqual(preview.customer_count, 1)

    def test_daily_backup_runs_once_and_cleans_old_files(self) -> None:
        self._create_customer("自动备份客户")
        first = asyncio.run(self.service.ensure_daily_backup())
        second = asyncio.run(self.service.ensure_daily_backup())
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertTrue(first.encrypted)
        self.assertTrue(first.filename.endswith(".enc"))

        old_file = self.root / "backups" / "daily" / "physio-daily-2020-01-01-old.physio-backup"
        old_file.write_bytes(b"old")
        asyncio.run(self.service.ensure_daily_backup())
        self.assertFalse(old_file.exists())

    def test_maintenance_removes_expired_temp_files_and_all_backup_kinds(
        self,
    ) -> None:
        old_timestamp = time.time() - 3600
        pending = self.service._pending_dir / "expired-restore"
        pending.mkdir(parents=True)
        preview = pending / "preview.json"
        preview.write_text(
            '{"expires_at": "2020-01-01T00:00:00+00:00"}',
            encoding="utf-8",
        )
        os.utime(preview, (old_timestamp, old_timestamp))
        os.utime(pending, (old_timestamp, old_timestamp))

        interrupted = self.root / ".customer.sqlite3.restore-abandoned"
        interrupted.write_bytes(b"temp")
        os.utime(interrupted, (old_timestamp, old_timestamp))

        rollback_temp = self.service._rollback_dir / "customer.rollback"
        rollback_temp.write_bytes(b"rollback")
        os.utime(rollback_temp, (old_timestamp, old_timestamp))

        temp_backup_dir = (
            self.service._backup_dir / "physio-backup-abandoned"
        )
        temp_backup_dir.mkdir()
        (temp_backup_dir / "snapshot").write_bytes(b"snapshot")
        os.utime(temp_backup_dir, (old_timestamp, old_timestamp))

        old_backups = (
            self.service._daily_dir
            / "physio-daily-2020-01-01-old.physio-backup",
            self.service._manual_dir
            / "physio-manual-20200101-120000-old.physio-backup.enc",
            self.service._rollback_dir
            / "physio-rollback-20200101-120000-old.physio-backup.enc",
        )
        for path in old_backups:
            path.write_bytes(b"old")

        kept_backup = (
            self.service._manual_dir
            / "physio-manual-29990101-120000-keep.physio-backup.enc"
        )
        kept_backup.write_bytes(b"keep")

        report = asyncio.run(self.service.run_maintenance())

        self.assertFalse(pending.exists())
        self.assertFalse(interrupted.exists())
        self.assertFalse(rollback_temp.exists())
        self.assertFalse(temp_backup_dir.exists())
        self.assertTrue(all(not path.exists() for path in old_backups))
        self.assertTrue(kept_backup.exists())
        self.assertGreaterEqual(report.expired_backups_removed, 3)
        self.assertGreaterEqual(report.temp_files_removed, 2)
        self.assertGreaterEqual(report.temp_directories_removed, 2)
        self.assertGreater(report.bytes_reclaimed, 0)

    def test_restore_api_round_trip(self) -> None:
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            app = create_app(
                replace(
                    settings,
                    customer_db_path=temp_path / "api-customer.sqlite3",
                    tool_audit_db_path=temp_path / "api-audit.sqlite3",
                    backup_dir=temp_path / "backups",
                    backup_auto_enabled=False,
                    backup_auto_password="rollback-test-pass-123",
                    staff_access_password="",
                )
            )
            with TestClient(app) as client:
                customer_a = client.post(
                    "/api/customers", json={"name": "接口备份客户"}
                ).json()
                exported = client.post("/api/backups/export", json={})
                self.assertEqual(exported.status_code, 200)
                backup_bytes = exported.content
                self.assertTrue(backup_bytes.startswith(b"PHYSIOENC1"))
                backups = client.get("/api/backups")
                self.assertEqual(backups.status_code, 200)
                self.assertEqual(len(backups.json()), 1)

                client.post(
                    "/api/customers", json={"name": "恢复后应消失"}
                )
                preview = client.post(
                    "/api/backups/restore/preview",
                    files={
                        "file": (
                            "backup.physio-backup",
                            backup_bytes,
                            "application/octet-stream",
                        )
                    },
                    data={"password": ""},
                )
                self.assertEqual(preview.status_code, 200)
                self.assertEqual(preview.json()["customer_count"], 1)
                confirmed = client.post(
                    "/api/backups/restore/confirm",
                    json={"restore_id": preview.json()["restore_id"]},
                )
                self.assertEqual(confirmed.status_code, 200)
                customers = client.get("/api/customers").json()
                self.assertEqual(
                    [customer["id"] for customer in customers],
                    [customer_a["id"]],
                )

    def test_app_lifespan_creates_daily_backup(self) -> None:
        from app.main import create_app

        settings = get_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            app = create_app(
                replace(
                    settings,
                    customer_db_path=temp_path / "auto-customer.sqlite3",
                    tool_audit_db_path=temp_path / "auto-audit.sqlite3",
                    backup_dir=temp_path / "backups",
                    backup_auto_enabled=True,
                    backup_auto_password="daily-test-pass-123",
                )
            )
            with TestClient(app):
                daily_dir = temp_path / "backups" / "daily"
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    if list(daily_dir.glob("physio-daily-*")):
                        break
                    time.sleep(0.05)
                self.assertEqual(
                    len(list(daily_dir.glob("physio-daily-*.enc"))), 1
                )


if __name__ == "__main__":
    unittest.main()
