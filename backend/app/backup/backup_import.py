"""Backup file import helpers (Chunk 14a + 15a).

Chunk 15a:
  - detect_format distinguishes LTPOS-BACKUP-V2 / LTPOS-BACKUP-V1 / SQL
  - inspect_metadata returns outer_sha256 (None for V1) and legacy flag
  - uses streaming hash from app.backup.service._stream_sha256
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.backup.service import (
    BackupError,
    MAGIC_V1,
    MAGIC_V2,
    _stream_sha256,
    decrypt_backup,
    get_outer_sha256_hex,
)

MAX_IMPORT_SIZE = 500 * 1024 * 1024  # 500 MB
ALLOWED_EXTENSIONS = (".ltbak", ".sql")


def validate_upload(upload: UploadFile) -> None:
    """Validate filename extension. File size is checked after reading."""
    name = (upload.filename or "").lower()
    if not name.endswith(ALLOWED_EXTENSIONS):
        raise BackupError("Unsupported file type. Allowed: " + ", ".join(ALLOWED_EXTENSIONS))


def read_and_hash(upload: UploadFile, max_size: int = MAX_IMPORT_SIZE) -> tuple[bytes, str]:
    """Read whole file, enforce size limit, return (bytes, sha256_hex).

    Chunk 15a: hash via streaming helper (64KB chunks). The bytes are
    still held in memory because Fernet decrypt requires the full
    payload - that is unavoidable for the V2 encrypted envelope.
    """
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
    sha256 = _stream_sha256(data)
    return data, sha256


def detect_format(data: bytes) -> str:
    """Detect .ltbak V2, .ltbak V1, or plain SQL dump."""
    if data.startswith(MAGIC_V2):
        return "LTPOS-BACKUP-V2"
    if data.startswith(MAGIC_V1):
        return "LTPOS-BACKUP-V1"
    return "SQL"


def inspect_metadata(data: bytes, secret: str) -> dict:
    """Extract .ltbak metadata. Raises BackupError if unreadable.

    Returns dict with these keys (all may be None for SQL dumps):
      format, created_at, sha256 (inner), outer_sha256, size, source,
      backup_point_id, shop_uuid, shop_name, schema_version,
      user_count, branch_count, legacy (True for V1 files)
    """
    fmt = detect_format(data)
    if fmt in ("LTPOS-BACKUP-V1", "LTPOS-BACKUP-V2"):
        try:
            meta, _raw = decrypt_backup(data, secret=secret)
        except BackupError as exc:
            raise BackupError(f"Cannot read backup metadata: {exc}") from exc
        return {
            "format": meta.get("format"),
            "created_at": meta.get("created_at"),
            "sha256": meta.get("sha256"),
            "outer_sha256": get_outer_sha256_hex(data),
            "size": meta.get("size"),
            "source": meta.get("source"),
            "backup_point_id": meta.get("backup_point_id"),
            "shop_uuid": meta.get("shop_uuid"),
            "shop_name": meta.get("shop_name"),
            "schema_version": meta.get("schema_version"),
            "user_count": meta.get("user_count"),
            "branch_count": meta.get("branch_count"),
            "legacy": bool(meta.get("_legacy")),
        }
    return {
        "format": "SQL",
        "created_at": None,
        "sha256": _stream_sha256(data),
        "outer_sha256": None,
        "size": len(data),
        "source": None,
        "backup_point_id": None,
        "shop_uuid": None,
        "shop_name": None,
        "schema_version": None,
        "user_count": None,
        "branch_count": None,
        "legacy": False,
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
