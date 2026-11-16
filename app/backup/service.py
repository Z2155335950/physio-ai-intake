from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.backup.models import (
    BackupInfo,
    BackupMaintenanceReport,
    RestorePreview,
    RestoreResult,
)


logger = logging.getLogger(__name__)

_ARCHIVE_MAGIC = b"PHYSIOENC1"
_KDF_ITERATIONS = 390_000
_MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
_MAX_EXTRACTED_BYTES = 500 * 1024 * 1024
_MANIFEST_NAME = "manifest.json"
_DATABASE_DIRECTORY = "databases"
_REQUIRED_CUSTOMER_TABLES = {
    "customers",
    "investigations",
    "followup_tasks",
    "appointments",
    "visit_completion_challenges",
}


class BackupError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class BackupService:
    def __init__(
        self,
        *,
        customer_db_path: Path,
        audit_db_path: Path,
        backup_dir: Path,
        automatic_password: str | None = None,
        retention_days: int = 30,
        restore_ttl_minutes: int = 10,
    ) -> None:
        self._database_paths = {
            "customer_memory.sqlite3": customer_db_path,
            "tool_audit.sqlite3": audit_db_path,
        }
        self._backup_dir = backup_dir
        self._manual_dir = backup_dir / "manual"
        self._daily_dir = backup_dir / "daily"
        self._rollback_dir = backup_dir / "rollback"
        self._pending_dir = backup_dir / ".restore-pending"
        for directory in (
            self._manual_dir,
            self._daily_dir,
            self._rollback_dir,
            self._pending_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        self._automatic_password = automatic_password or ""
        self._retention_days = retention_days
        self._restore_ttl_minutes = restore_ttl_minutes
        self._lock = asyncio.Lock()

    async def create_backup(
        self,
        *,
        password: str | None = None,
        kind: str = "manual",
    ) -> BackupInfo:
        async with self._lock:
            return await asyncio.to_thread(
                self._create_backup_sync, password, kind
            )

    async def export_bytes(
        self, *, password: str | None = None
    ) -> tuple[bytes, BackupInfo]:
        async with self._lock:
            info, path = await asyncio.to_thread(
                self._create_backup_file_sync, password, "manual"
            )
            content = await asyncio.to_thread(path.read_bytes)
            return content, info

    async def list_backups(self) -> list[BackupInfo]:
        async with self._lock:
            return await asyncio.to_thread(self._list_backups_sync)

    async def get_backup_path(self, filename: str) -> Path:
        if Path(filename).name != filename:
            raise BackupError("invalid_filename", "非法备份文件名")
        for directory in (self._manual_dir, self._daily_dir):
            candidate = directory / filename
            if candidate.is_file():
                return candidate
        raise BackupError("backup_not_found", "备份文件不存在")

    async def preview_restore(
        self, content: bytes, password: str | None = None
    ) -> RestorePreview:
        async with self._lock:
            return await asyncio.to_thread(
                self._preview_restore_sync, content, password
            )

    async def confirm_restore(self, restore_id: str) -> RestoreResult:
        async with self._lock:
            return await asyncio.to_thread(
                self._confirm_restore_sync, restore_id
            )

    async def ensure_daily_backup(
        self, password: str | None = None
    ) -> BackupInfo | None:
        async with self._lock:
            return await asyncio.to_thread(
                self._ensure_daily_backup_sync, password
            )

    async def run_maintenance(self) -> BackupMaintenanceReport:
        async with self._lock:
            return await asyncio.to_thread(self._run_maintenance_sync)

    async def run_daily_loop(
        self,
        *,
        password: str | None,
        enabled: asyncio.Event,
    ) -> None:
        while not enabled.is_set():
            try:
                await self.ensure_daily_backup(password)
            except Exception:
                logger.exception("自动每日备份失败")
            try:
                await asyncio.wait_for(enabled.wait(), timeout=3600)
            except asyncio.TimeoutError:
                continue

    async def run_maintenance_loop(self, *, enabled: asyncio.Event) -> None:
        while not enabled.is_set():
            try:
                await self.run_maintenance()
            except Exception:
                logger.exception("备份临时文件清理失败")
            try:
                await asyncio.wait_for(enabled.wait(), timeout=3600)
            except asyncio.TimeoutError:
                continue

    def _create_backup_sync(
        self, password: str | None, kind: str
    ) -> BackupInfo:
        info, _ = self._create_backup_file_sync(password, kind)
        return info

    def _create_backup_file_sync(
        self, password: str | None, kind: str
    ) -> tuple[BackupInfo, Path]:
        password = self._resolve_encryption_password(password)
        archive_bytes, manifest = self._build_archive_bytes()
        now = datetime.now(timezone.utc)
        payload = self._encrypt_archive(archive_bytes, password)

        if kind == "daily":
            prefix = f"physio-daily-{now.astimezone().date().isoformat()}"
            directory = self._daily_dir
        elif kind == "rollback":
            prefix = f"physio-rollback-{now.astimezone().strftime('%Y%m%d-%H%M%S')}"
            directory = self._rollback_dir
        else:
            kind = "manual"
            prefix = f"physio-manual-{now.astimezone().strftime('%Y%m%d-%H%M%S')}"
            directory = self._manual_dir
        filename = f"{prefix}-{uuid.uuid4().hex[:6]}.physio-backup.enc"
        path = directory / filename
        path.write_bytes(payload)
        return (
            BackupInfo(
                filename=filename,
                kind=kind,
                created_at=datetime.fromisoformat(manifest["created_at"]),
                size_bytes=len(payload),
                encrypted=True,
            ),
            path,
        )

    def _resolve_encryption_password(
        self, password: str | None
    ) -> str:
        resolved = password or self._automatic_password
        if not resolved:
            raise BackupError(
                "encryption_password_required",
                "未配置备份加密密码，已拒绝创建未加密备份",
            )
        if len(resolved) < 8:
            raise BackupError(
                "weak_password", "备份密码至少需要 8 个字符"
            )
        return resolved

    def _build_archive_bytes(self) -> tuple[bytes, dict]:
        manifest = {
            "format": "physio-assistant-backup",
            "version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            ),
            "database_files": {},
        }
        buffer = io.BytesIO()
        with tempfile.TemporaryDirectory(
            prefix="physio-backup-", dir=self._backup_dir
        ) as temp_dir:
            temp_path = Path(temp_dir)
            with zipfile.ZipFile(
                buffer, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                for archive_name, source_path in self._database_paths.items():
                    if not source_path.exists():
                        raise BackupError(
                            "database_missing",
                            f"数据库不存在: {source_path.name}",
                        )
                    snapshot_path = temp_path / archive_name
                    self._snapshot_sqlite(source_path, snapshot_path)
                    content = snapshot_path.read_bytes()
                    manifest["database_files"][archive_name] = {
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "size": len(content),
                    }
                    archive.write(
                        snapshot_path,
                        f"{_DATABASE_DIRECTORY}/{archive_name}",
                    )
                archive.writestr(
                    _MANIFEST_NAME,
                    json.dumps(manifest, ensure_ascii=False, indent=2),
                )
        return buffer.getvalue(), manifest

    def _preview_restore_sync(
        self, content: bytes, password: str | None
    ) -> RestorePreview:
        if len(content) > _MAX_ARCHIVE_BYTES:
            raise BackupError(
                "archive_too_large", "备份文件超过允许大小"
            )
        encrypted = content.startswith(_ARCHIVE_MAGIC)
        if encrypted:
            password = self._resolve_encryption_password(password)
            archive_bytes = self._decrypt_archive(content, password)
        else:
            archive_bytes = content
        if not zipfile.is_zipfile(io.BytesIO(archive_bytes)):
            raise BackupError("invalid_archive", "不是有效的备份文件")

        restore_id = str(uuid.uuid4())
        restore_dir = self._pending_dir / restore_id
        restore_dir.mkdir(parents=True)
        try:
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
                total_size = sum(info.file_size for info in archive.infolist())
                if total_size > _MAX_EXTRACTED_BYTES:
                    raise BackupError(
                        "archive_too_large", "备份解压后体积超过限制"
                    )
                names = set(archive.namelist())
                if _MANIFEST_NAME not in names:
                    raise BackupError(
                        "manifest_missing", "备份缺少 manifest"
                    )
                manifest = json.loads(
                    archive.read(_MANIFEST_NAME).decode("utf-8")
                )
                if manifest.get("format") != "physio-assistant-backup":
                    raise BackupError(
                        "invalid_manifest", "备份格式不受支持"
                    )
                manifest_databases = manifest.get("database_files", {})
                missing_databases = sorted(
                    set(self._database_paths) - set(manifest_databases)
                )
                if missing_databases:
                    raise BackupError(
                        "database_missing",
                        f"备份缺少数据库：{', '.join(missing_databases)}",
                    )
                for archive_name, expected in manifest_databases.items():
                    if archive_name not in self._database_paths:
                        raise BackupError(
                            "unexpected_database", "备份包含未知数据库"
                        )
                    member = f"{_DATABASE_DIRECTORY}/{archive_name}"
                    if member not in names:
                        raise BackupError(
                            "database_missing", f"备份缺少 {archive_name}"
                        )
                    target = restore_dir / archive_name
                    target.write_bytes(archive.read(member))
                    digest = hashlib.sha256(target.read_bytes()).hexdigest()
                    if digest != expected.get("sha256"):
                        raise BackupError(
                            "checksum_mismatch",
                            f"{archive_name} 校验失败",
                        )
                    self._validate_sqlite(target)

            customer_path = restore_dir / "customer_memory.sqlite3"
            if not customer_path.exists():
                raise BackupError(
                    "database_missing", "备份缺少客户数据库"
                )
            self._validate_customer_schema(customer_path)
            counts = self._database_counts(customer_path)
            expires_at = datetime.now(timezone.utc) + timedelta(
                minutes=self._restore_ttl_minutes
            )
            metadata = {
                "restore_id": restore_id,
                "backup_created_at": manifest["created_at"],
                "expires_at": expires_at.isoformat(timespec="seconds"),
                "encrypted": encrypted,
                "counts": counts,
                "database_files": sorted(
                    manifest.get("database_files", {}).keys()
                ),
            }
            (restore_dir / "preview.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return RestorePreview(
                restore_id=restore_id,
                backup_created_at=datetime.fromisoformat(
                    manifest["created_at"]
                ),
                expires_at=expires_at,
                encrypted=encrypted,
                **counts,
                database_files=metadata["database_files"],
                warning=(
                    "恢复会覆盖当前客户数据。确认前系统会额外生成一份当前数据安全备份。"
                ),
            )
        except BackupError:
            shutil.rmtree(restore_dir, ignore_errors=True)
            raise
        except Exception as exc:
            shutil.rmtree(restore_dir, ignore_errors=True)
            raise BackupError(
                "invalid_archive", "备份文件解析失败"
            ) from exc

    def _confirm_restore_sync(self, restore_id: str) -> RestoreResult:
        if Path(restore_id).name != restore_id:
            raise BackupError("invalid_restore_id", "非法恢复标识")
        restore_dir = self._pending_dir / restore_id
        preview_path = restore_dir / "preview.json"
        if not preview_path.exists():
            raise BackupError("restore_not_found", "待恢复备份不存在")
        metadata = json.loads(preview_path.read_text(encoding="utf-8"))
        expires_at = datetime.fromisoformat(metadata["expires_at"])
        if expires_at < datetime.now(timezone.utc):
            shutil.rmtree(restore_dir, ignore_errors=True)
            raise BackupError("restore_expired", "恢复确认已过期")

        safety_password = self._resolve_encryption_password(None)
        safety_info, rollback_path = self._create_backup_file_sync(
            safety_password, "rollback"
        )
        archive_bytes = self._decrypt_archive(
            rollback_path.read_bytes(), safety_password
        )

        replaced: list[tuple[Path, Path]] = []
        rollback_copies: list[Path] = []
        try:
            for archive_name, target_path in self._database_paths.items():
                source = restore_dir / archive_name
                if not source.exists():
                    raise BackupError(
                        "database_missing", f"待恢复数据缺少 {archive_name}"
                    )
                target_path.parent.mkdir(parents=True, exist_ok=True)
                rollback_copy = rollback_path.with_name(
                    f"{archive_name}.rollback"
                )
                self._extract_database_from_archive(
                    archive_bytes, archive_name, rollback_copy
                )
                rollback_copies.append(rollback_copy)
                self._validate_sqlite(rollback_copy)
                temporary = target_path.with_name(
                    f".{target_path.name}.restore-{uuid.uuid4().hex}"
                )
                shutil.copy2(source, temporary)
                for suffix in ("-wal", "-shm", "-journal"):
                    Path(f"{target_path}{suffix}").unlink(missing_ok=True)
                os.replace(temporary, target_path)
                replaced.append((target_path, rollback_copy))
        except Exception as exc:
            for target_path, rollback_copy in reversed(replaced):
                try:
                    os.replace(rollback_copy, target_path)
                except Exception:
                    logger.exception("恢复失败后回滚数据库失败")
            if isinstance(exc, BackupError):
                raise
            raise BackupError("restore_failed", "恢复数据库失败") from exc
        finally:
            shutil.rmtree(restore_dir, ignore_errors=True)
            for rollback_copy in rollback_copies:
                try:
                    rollback_copy.unlink(missing_ok=True)
                except OSError:
                    logger.exception("清理恢复临时回滚文件失败")

        customer_path = self._database_paths["customer_memory.sqlite3"]
        counts = self._database_counts(customer_path)
        return RestoreResult(
            restored=True,
            **counts,
            safety_backup=safety_info.filename,
        )

    def _ensure_daily_backup_sync(
        self, password: str | None
    ) -> BackupInfo | None:
        date_label = datetime.now().astimezone().date().isoformat()
        existing = list(
            self._daily_dir.glob(f"physio-daily-{date_label}-*.enc")
        )
        if existing:
            self._cleanup_expired_backups_sync()
            return None
        info, _ = self._create_backup_file_sync(password, "daily")
        self._cleanup_expired_backups_sync()
        return info

    def _run_maintenance_sync(self) -> BackupMaintenanceReport:
        now = datetime.now(timezone.utc)
        expired = self._cleanup_expired_backups_sync()
        temp_files, temp_directories, bytes_reclaimed = (
            self._cleanup_expired_temp_files_sync(now)
        )
        return BackupMaintenanceReport(
            checked_at=now,
            expired_backups_removed=expired,
            temp_files_removed=temp_files,
            temp_directories_removed=temp_directories,
            bytes_reclaimed=bytes_reclaimed,
        )

    def _cleanup_expired_backups_sync(self) -> int:
        cutoff = datetime.now().astimezone().date() - timedelta(
            days=self._retention_days
        )
        removed = 0
        for directory, kind in (
            (self._daily_dir, "daily"),
            (self._manual_dir, "manual"),
            (self._rollback_dir, "rollback"),
        ):
            for path in directory.glob("*.physio-backup*"):
                if not path.is_file():
                    continue
                file_date = self._backup_file_date(path, kind)
                if file_date < cutoff:
                    path.unlink(missing_ok=True)
                    removed += 1
        return removed

    def _cleanup_expired_temp_files_sync(
        self, now: datetime
    ) -> tuple[int, int, int]:
        cutoff = now - timedelta(minutes=self._restore_ttl_minutes)
        removed_files = 0
        removed_directories = 0
        bytes_reclaimed = 0

        for entry in self._pending_dir.iterdir():
            expired = self._mtime_before(entry, cutoff)
            if entry.is_dir():
                preview_path = entry / "preview.json"
                if preview_path.exists():
                    try:
                        preview = json.loads(
                            preview_path.read_text(encoding="utf-8")
                        )
                        expired = (
                            datetime.fromisoformat(preview["expires_at"]) < now
                        )
                    except (KeyError, ValueError, OSError, json.JSONDecodeError):
                        expired = True
            if expired:
                files, directories, size = self._safe_remove(
                    self._pending_dir, entry
                )
                removed_files += files
                removed_directories += directories
                bytes_reclaimed += size

        for database_path in self._database_paths.values():
            for pattern in (
                f".{database_path.name}.restore-*",
                f"{database_path.name}.rollback",
            ):
                for path in database_path.parent.glob(pattern):
                    if path.is_file() and self._mtime_before(path, cutoff):
                        files, directories, size = self._safe_remove(
                            database_path.parent, path
                        )
                        removed_files += files
                        removed_directories += directories
                        bytes_reclaimed += size

        for path in self._rollback_dir.glob("*.rollback"):
            if path.is_file() and self._mtime_before(path, cutoff):
                files, directories, size = self._safe_remove(
                    self._rollback_dir, path
                )
                removed_files += files
                removed_directories += directories
                bytes_reclaimed += size

        for path in self._backup_dir.glob("physio-backup-*"):
            if path.is_dir() and self._mtime_before(path, cutoff):
                files, directories, size = self._safe_remove(
                    self._backup_dir, path
                )
                removed_files += files
                removed_directories += directories
                bytes_reclaimed += size

        return removed_files, removed_directories, bytes_reclaimed

    @staticmethod
    def _mtime_before(path: Path, cutoff: datetime) -> bool:
        try:
            return (
                datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                < cutoff
            )
        except OSError:
            return False

    @staticmethod
    def _backup_file_date(path: Path, kind: str) -> date:
        try:
            if kind == "daily":
                return datetime.strptime(
                    "-".join(path.name.split("-")[2:5]), "%Y-%m-%d"
                ).date()
            prefix = f"physio-{kind}-"
            date_text = path.name.removeprefix(prefix).split("-", 1)[0]
            return datetime.strptime(date_text, "%Y%m%d").date()
        except (ValueError, IndexError):
            return datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).astimezone().date()

    @classmethod
    def _safe_remove(
        cls, root: Path, target: Path
    ) -> tuple[int, int, int]:
        root_resolved = root.resolve()
        target_resolved = target.resolve()
        if target_resolved == root_resolved or (
            root_resolved not in target_resolved.parents
        ):
            return 0, 0, 0
        files = 0
        directories = 0
        size = 0
        if target_resolved.is_dir():
            for child in target_resolved.rglob("*"):
                if child.is_file():
                    files += 1
                    try:
                        size += child.stat().st_size
                    except OSError:
                        pass
            directories = 1
            shutil.rmtree(target_resolved, ignore_errors=True)
        elif target_resolved.is_file():
            try:
                size = target_resolved.stat().st_size
                target_resolved.unlink()
                files = 1
            except OSError:
                return 0, 0, 0
        return files, directories, size

    def _list_backups_sync(self) -> list[BackupInfo]:
        items: list[BackupInfo] = []
        for directory, kind in (
            (self._manual_dir, "manual"),
            (self._daily_dir, "daily"),
        ):
            for path in directory.glob("*.physio-backup*"):
                info = self._backup_info(path, kind)
                if info:
                    items.append(info)
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items

    def _backup_info(self, path: Path, kind: str) -> BackupInfo | None:
        try:
            created_at = datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            )
            return BackupInfo(
                filename=path.name,
                kind=kind,
                created_at=created_at,
                size_bytes=path.stat().st_size,
                encrypted=path.name.endswith(".enc"),
            )
        except OSError:
            return None

    @staticmethod
    def _snapshot_sqlite(source: Path, target: Path) -> None:
        source_connection = sqlite3.connect(source, timeout=15)
        target_connection = sqlite3.connect(target, timeout=15)
        try:
            source_connection.backup(target_connection)
        finally:
            target_connection.close()
            source_connection.close()
        BackupService._validate_sqlite(target)

    @staticmethod
    def _validate_sqlite(path: Path) -> None:
        try:
            connection = sqlite3.connect(path)
            try:
                result = connection.execute(
                    "PRAGMA integrity_check"
                ).fetchone()
                if not result or result[0] != "ok":
                    raise BackupError(
                        "database_integrity_failed", "数据库完整性校验失败"
                    )
            finally:
                connection.close()
        except sqlite3.DatabaseError as exc:
            raise BackupError(
                "database_invalid", "数据库文件无法读取"
            ) from exc

    @staticmethod
    def _validate_customer_schema(path: Path) -> None:
        connection = sqlite3.connect(path)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
        finally:
            connection.close()
        missing = sorted(_REQUIRED_CUSTOMER_TABLES - tables)
        if missing:
            raise BackupError(
                "schema_mismatch",
                f"客户数据库缺少必要表：{', '.join(missing)}",
            )

    @staticmethod
    def _database_counts(path: Path) -> dict[str, int]:
        connection = sqlite3.connect(path)
        try:
            return {
                "customer_count": connection.execute(
                    "SELECT COUNT(*) FROM customers"
                ).fetchone()[0],
                "investigation_count": connection.execute(
                    "SELECT COUNT(*) FROM investigations"
                ).fetchone()[0],
                "appointment_count": connection.execute(
                    "SELECT COUNT(*) FROM appointments"
                ).fetchone()[0],
                "followup_count": connection.execute(
                    "SELECT COUNT(*) FROM followup_tasks"
                ).fetchone()[0],
            }
        finally:
            connection.close()

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        derivation = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=_KDF_ITERATIONS,
        )
        return derivation.derive(password.encode("utf-8"))

    @classmethod
    def _encrypt_archive(cls, content: bytes, password: str) -> bytes:
        salt = os.urandom(16)
        nonce = os.urandom(12)
        encrypted = AESGCM(cls._derive_key(password, salt)).encrypt(
            nonce, content, _ARCHIVE_MAGIC
        )
        return _ARCHIVE_MAGIC + salt + nonce + encrypted

    @classmethod
    def _decrypt_archive(cls, content: bytes, password: str) -> bytes:
        if len(content) < len(_ARCHIVE_MAGIC) + 28:
            raise BackupError("invalid_archive", "加密备份文件损坏")
        offset = len(_ARCHIVE_MAGIC)
        salt = content[offset : offset + 16]
        nonce = content[offset + 16 : offset + 28]
        ciphertext = content[offset + 28 :]
        try:
            return AESGCM(cls._derive_key(password, salt)).decrypt(
                nonce, ciphertext, _ARCHIVE_MAGIC
            )
        except InvalidTag as exc:
            raise BackupError(
                "invalid_backup_password", "备份密码错误"
            ) from exc

    @staticmethod
    def _extract_database_from_archive(
        archive_bytes: bytes, archive_name: str, target: Path
    ) -> None:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            target.write_bytes(
                archive.read(f"{_DATABASE_DIRECTORY}/{archive_name}")
            )
