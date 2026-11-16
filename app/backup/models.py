from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BackupInfo(BaseModel):
    filename: str
    kind: str
    created_at: datetime
    size_bytes: int
    encrypted: bool


class BackupExportRequest(BaseModel):
    password: str | None = Field(
        default=None, min_length=8, max_length=128
    )


class RestorePreview(BaseModel):
    restore_id: str
    backup_created_at: datetime
    expires_at: datetime
    encrypted: bool
    customer_count: int
    investigation_count: int
    appointment_count: int
    followup_count: int
    database_files: list[str] = Field(default_factory=list)
    warning: str


class RestoreConfirmRequest(BaseModel):
    restore_id: str


class RestoreResult(BaseModel):
    restored: bool
    customer_count: int
    investigation_count: int
    safety_backup: str


class BackupMaintenanceReport(BaseModel):
    checked_at: datetime
    expired_backups_removed: int = 0
    temp_files_removed: int = 0
    temp_directories_removed: int = 0
    bytes_reclaimed: int = 0

