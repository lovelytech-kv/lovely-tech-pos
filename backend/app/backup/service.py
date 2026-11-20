"""Lovely Tech POS backup format V2 (Chunk 15a).

Format history:
  V1 (Chunk 14a — before 2026-11-14):
    MAGIC_V1 = b"LTPOS-BACKUP-V1\n"
    || Fernet(metadata_json + b"\n" + raw_pg_dump)
    Inner metadata: sha256(raw) and size — verified after decrypt.

  V2 (Chunk 15a — current):
    MAGIC_V2 = b"LTPOS-BACKUP-V2\n"
    || outer_sha256 (32 raw bytes) = sha256(fernet_payload)
    || Fernet(metadata_json + b"\n" + raw_pg_dump)
    Outer hash verified BEFORE any decrypt attempt → fail-fast on
    tamper / silent corruption. Inner sha256 still verified after.

Both V1 and V2 are readable forever. Only V2 is written going forward.
V1 files return metadata["_legacy"]=True so the UI can prompt for
explicit user acknowledgement before restore.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Union

from cryptography.fernet import Fernet, InvalidToken

MAGIC_V1 = b"LTPOS-BACKUP-V1\n"
MAGIC_V2 = b"LTPOS-BACKUP-V2\n"
# Backwards-compat alias — existing imports elsewhere use MAGIC for V1 detect.
MAGIC = MAGIC_V1

_HASH_CHUNK = 64 * 1024
_OUTER_SHA_BYTES = 32  # raw sha256 digest size


class BackupError(ValueError):
    pass


def _stream_sha256(source: Union[bytes, bytearray, IO[bytes]],
                   chunk_size: int = _HASH_CHUNK) -> str:
    """SHA-256 streaming (64 KB chunks). Accepts bytes or file-like.

    Manager rule (Chunk 15a, caveat 2): never load the whole file into
    memory just to hash. For bytes we still iterate in chunks — single
    code path so swapping to a disk stream later is a no-op.
    """
    h = hashlib.sha256()
    if hasattr(source, "read"):
        while True:
            chunk = source.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    else:
        data = source if isinstance(source, (bytes, bytearray)) else bytes(source)
        for i in range(0, len(data), chunk_size):
            h.update(data[i:i + chunk_size])
    return h.hexdigest()


def hash_file_streaming(path: Path, chunk_size: int = _HASH_CHUNK) -> str:
    """Stream SHA-256 of a file from disk (no full-file load)."""
    with Path(path).open("rb") as f:
        return _stream_sha256(f, chunk_size)


def get_outer_sha256_hex(blob: bytes) -> str | None:
    """Hex of V2 outer sha256 (for audit logs). None for V1 or truncated."""
    if not blob.startswith(MAGIC_V2):
        return None
    header_end = len(MAGIC_V2) + _OUTER_SHA_BYTES
    if len(blob) < header_end:
        return None
    return blob[len(MAGIC_V2):header_end].hex()


def libpq_url(database_url: str) -> str:
    """pg_dump/pg_restore/psql only understand postgresql://, not the SQLAlchemy driver form."""
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://", "postgres+psycopg://"):
        if database_url.startswith(prefix):
            return "postgresql://" + database_url[len(prefix):]
    return database_url


def derive_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_backup(raw: bytes, *, secret: str, metadata: dict | None = None) -> bytes:
    """Encrypt raw payload to V2 format (MAGIC_V2 || outer_sha256 || fernet)."""
    if not raw:
        raise BackupError("Backup payload is empty")
    meta = dict(metadata or {})
    meta.update({
        "format": "LTPOS-BACKUP-V2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
    })
    envelope = json.dumps(meta, sort_keys=True, separators=(",", ":")).encode() + b"\n" + raw
    fernet_payload = Fernet(derive_key(secret)).encrypt(envelope)
    outer = hashlib.sha256(fernet_payload).digest()
    return MAGIC_V2 + outer + fernet_payload


def decrypt_backup(blob: bytes, *, secret: str) -> tuple[dict, bytes]:
    """Decrypt V2 or V1 .ltbak. V2 verifies outer sha256 BEFORE decrypt attempt.

    Returns (metadata, raw). metadata["_legacy"]=True for V1 files.
    """
    if blob.startswith(MAGIC_V2):
        header_end = len(MAGIC_V2) + _OUTER_SHA_BYTES
        if len(blob) < header_end:
            raise BackupError("Backup file is truncated (V2 header incomplete)")
        expected_outer = blob[len(MAGIC_V2):header_end]
        fernet_payload = blob[header_end:]
        actual_outer = hashlib.sha256(fernet_payload).digest()
        if actual_outer != expected_outer:
            raise BackupError(
                "Backup file integrity check failed: outer hash mismatch "
                "(file may be corrupted or tampered)"
            )
        try:
            envelope = Fernet(derive_key(secret)).decrypt(fernet_payload)
        except InvalidToken as exc:
            raise BackupError("Backup authentication failed") from exc
        meta_raw, raw = envelope.split(b"\n", 1)
        meta = json.loads(meta_raw.decode())
        if hashlib.sha256(raw).hexdigest() != meta.get("sha256") or len(raw) != meta.get("size"):
            raise BackupError("Backup inner integrity check failed")
        meta["_legacy"] = False
        return meta, raw

    if blob.startswith(MAGIC_V1):
        try:
            envelope = Fernet(derive_key(secret)).decrypt(blob[len(MAGIC_V1):])
        except InvalidToken as exc:
            raise BackupError("Backup authentication failed") from exc
        meta_raw, raw = envelope.split(b"\n", 1)
        meta = json.loads(meta_raw.decode())
        if hashlib.sha256(raw).hexdigest() != meta.get("sha256") or len(raw) != meta.get("size"):
            raise BackupError("Backup integrity check failed")
        meta["_legacy"] = True
        return meta, raw

    raise BackupError(
        "Unsupported backup format (expected LTPOS-BACKUP-V1 or LTPOS-BACKUP-V2)"
    )


def write_verified_backup(raw: bytes, destination: str | Path, *, secret: str,
                          metadata: dict | None = None) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    blob = encrypt_backup(raw, secret=secret, metadata=metadata)
    tmp = destination.with_suffix(destination.suffix + ".tmp")
    tmp.write_bytes(blob)
    check = tmp.read_bytes()
    decrypt_backup(check, secret=secret)
    os.replace(tmp, destination)
    return destination


def create_postgres_dump(*, pg_dump: str, database_url: str, destination: Path,
                         secret: str, metadata: dict | None = None) -> Path:
    database_url = libpq_url(database_url)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        raw_dump = Path(td) / "database.dump"
        subprocess.run(
            [pg_dump, "--format=custom", "--no-owner", "--no-privileges",
             "--file", str(raw_dump), database_url],
            env=os.environ.copy(), check=True, capture_output=True, text=True, timeout=300,
        )
        return write_verified_backup(
            raw_dump.read_bytes(), destination, secret=secret,
            metadata={"source": "pg_dump", "format": "custom", **(metadata or {})},
        )


def _terminate_other_connections(*, psql: str, database_url: str) -> None:
    """H13 — drop other backends before pg_restore --clean.

    Best-effort: a backend may exit between listing and termination, and a
    cleanup failure must not abort an otherwise valid restore attempt.
    """
    subprocess.run(
        [psql, "--dbname", database_url, "--command",
         "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
         "WHERE datname = current_database() AND pid <> pg_backend_pid();"],
        env=os.environ.copy(), check=False, capture_output=True, text=True, timeout=60,
    )


def restore_postgres_backup(*, pg_dump: str, pg_restore: str, psql: str,
                            database_url: str, encrypted_backup: Path,
                            safety_output: Path, secret: str,
                            engine=None) -> Path:
    """Restore a verified Lovely Tech encrypted custom-format dump.

    Explicit operator action. Safety backup is created and verified
    before pg_restore is allowed to replace the database.

    H13 — when the caller passes its SQLAlchemy Engine, the pool is disposed
    and other database backends are terminated before ``pg_restore --clean``
    so idle pooled connections cannot hold locks on objects being dropped.
    The engine is disposed again after restore so the next request opens a
    fresh session against the restored database.
    """
    database_url = libpq_url(database_url)
    if not encrypted_backup.exists():
        raise BackupError("Backup file not found")
    meta, raw_dump = decrypt_backup(encrypted_backup.read_bytes(), secret=secret)
    fmt = meta.get("format")
    if fmt not in ("LTPOS-BACKUP-V1", "LTPOS-BACKUP-V2"):
        raise BackupError("Unsupported backup envelope")
    safety_output = Path(safety_output)
    safety_output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        safety_raw = Path(td) / "safety.dump"
        subprocess.run(
            [pg_dump, "--format=custom", "--no-owner", "--no-privileges",
             "--file", str(safety_raw), database_url],
            env=os.environ.copy(), check=True, capture_output=True, text=True, timeout=300,
        )
        write_verified_backup(
            safety_raw.read_bytes(), safety_output, secret=secret,
            metadata={"source": "pre_restore_safety_backup", "format": "custom"},
        )
        restore_raw = Path(td) / "restore.dump"
        restore_raw.write_bytes(raw_dump)
        # H13 — release the pool and terminate other backends before --clean.
        if engine is not None:
            engine.dispose()
        _terminate_other_connections(psql=psql, database_url=database_url)
        subprocess.run(
            [pg_restore, "--clean", "--if-exists", "--no-owner", "--no-privileges",
             "--exit-on-error", "--dbname", database_url, str(restore_raw)],
            env=os.environ.copy(), check=True, capture_output=True, text=True, timeout=900,
        )
        subprocess.run(
            [psql, "--dbname", database_url, "--command", "SELECT 1;"],
            env=os.environ.copy(), check=True, capture_output=True, text=True, timeout=60,
        )
        # Drop any connection opened during the restore window so callers
        # reconnect to the restored database, never to pre-restore state.
        if engine is not None:
            engine.dispose()
    return safety_output


def sync_backup_to_google_drive(*, rclone_bin: str, remote: str, remote_path: str,
                                local_file: Path) -> str:
    if not remote:
        raise BackupError("Google Drive rclone remote is not configured")
    if not local_file.exists():
        raise BackupError("Local verified backup file not found")
    target = f"{remote.rstrip(chr(58))}:{remote_path.strip(chr(47))}/"
    subprocess.run(
        [rclone_bin, "copyto", str(local_file), f"{target}{local_file.name}", "--immutable"],
        check=True, capture_output=True, text=True, timeout=300,
    )
    check = subprocess.run(
        [rclone_bin, "lsl", f"{target}{local_file.name}"],
        check=True, capture_output=True, text=True, timeout=60,
    )
    if local_file.name not in check.stdout:
        raise BackupError("Google Drive verification failed")
    return f"{target}{local_file.name}"
