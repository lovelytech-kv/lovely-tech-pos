"""Backup file import helpers (Chunk 14a)."""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.backup.service import BackupError, decrypt_backup

MAX_IMPORT_SIZE = 500 * 1024 * 1024  # 500 MB
ALLOWED_EXTENSIONS = (".ltbak", ".sql")
MAGIC = b"LTPOS-BACKUP-V1\n"


def validate_upload(upload: UploadFile) -> None:
    """Validate filename extension. File size is checked after reading."""
    name = (upload.filename or "").lower()
    if not name.endswith(ALLOWED_EXTENSIONS):
        raise BackupError(
            f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )


def read_and_hash(upload: UploadFile, max_size: int = MAX_IMPORT_SIZE) -> tuple[bytes, str]:
    """Read the whole file, enforce size limit, return (bytes, sha256_hex)."""
    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(0)
    if size == 0:
        raise BackupError("Empty file")
    if size > max_size:
        raise BackupError(f"File too large ({size} bytes; max {max_size})")
    data = upload.file.read()
    if not data:
        raise BackupError("Empty file")
    return data, hashlib.sha256(data).hexdigest()


def detect_format(data: bytes) -> str:
    return "LTPOS-BACKUP-V1" if data.startswith(MAGIC) else "SQL"


def inspect_metadata(data: bytes, secret: str) -> dict:
    """Best-effort metadata extraction. Raises BackupError if .ltbak cannot be decrypted."""
    fmt = detect_format(data)
    if fmt == "LTPOS-BACKUP-V1":
        try:
            meta, _raw = decrypt_backup(data, secret=secret)
        except BackupError as exc:
            raise BackupError(f"Cannot read backup metadata: {exc}") from exc
        return {
            "format": "LTPOS-BACKUP-V1",
            "created_at": meta.get("created_at"),
            "sha256": meta.get("sha256"),
            "size": meta.get("size"),
            "source": meta.get("source"),
            "backup_point_id": meta.get("backup_point_id"),
            "shop_uuid": meta.get("shop_uuid"),
        }
    return {
        "format": "SQL",
        "created_at": None,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "source": None,
        "backup_point_id": None,
        "shop_uuid": None,
    }


def save_import_file(data: bytes, original_filename: str, backup_root: str) -> Path:
    """Save to {BACKUP_ROOT}/imports/{uuid}-{safe_name}. Returns absolute path."""
    imports_dir = (Path(backup_root).resolve() / "imports")
    imports_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if (c.isalnum() or c in "._-") else "_" for c in original_filename)
    safe = safe[-180:] if len(safe) > 180 else safe
    dest = imports_dir / f"{uuid.uuid4().hex}-{safe}"
    dest.write_bytes(data)
    return dest