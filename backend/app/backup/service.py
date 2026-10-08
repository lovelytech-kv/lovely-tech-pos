from __future__ import annotations
import base64, hashlib, json, os, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken

MAGIC = b"LTPOS-BACKUP-V1\n"

class BackupError(ValueError):
    pass


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
    if not raw:
        raise BackupError("Backup payload is empty")
    meta = dict(metadata or {})
    meta.update({"format": "LTPOS-BACKUP-V1", "created_at": datetime.now(timezone.utc).isoformat(), "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)})
    envelope = json.dumps(meta, sort_keys=True, separators=(",", ":")).encode() + b"\n" + raw
    return MAGIC + Fernet(derive_key(secret)).encrypt(envelope)

def decrypt_backup(blob: bytes, *, secret: str) -> tuple[dict, bytes]:
    if not blob.startswith(MAGIC):
        raise BackupError("Unsupported backup format")
    try:
        payload = Fernet(derive_key(secret)).decrypt(blob[len(MAGIC):])
    except InvalidToken as exc:
        raise BackupError("Backup authentication failed") from exc
    meta_raw, raw = payload.split(b"\n", 1)
    meta = json.loads(meta_raw.decode())
    if hashlib.sha256(raw).hexdigest() != meta.get("sha256") or len(raw) != meta.get("size"):
        raise BackupError("Backup integrity check failed")
    return meta, raw

def write_verified_backup(raw: bytes, destination: str | Path, *, secret: str, metadata: dict | None = None) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    blob = encrypt_backup(raw, secret=secret, metadata=metadata)
    tmp = destination.with_suffix(destination.suffix + ".tmp")
    tmp.write_bytes(blob)
    check = tmp.read_bytes()
    decrypt_backup(check, secret=secret)
    os.replace(tmp, destination)
    return destination


def create_postgres_dump(*, pg_dump: str, database_url: str, destination: Path, secret: str, metadata: dict | None = None) -> Path:
    database_url = libpq_url(database_url)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        raw_dump = Path(td) / "database.dump"
        subprocess.run(
            [pg_dump, "--format=custom", "--no-owner", "--no-privileges", "--file", str(raw_dump), database_url],
            env=os.environ.copy(), check=True, capture_output=True, text=True, timeout=300,
        )
        return write_verified_backup(raw_dump.read_bytes(), destination, secret=secret, metadata={"source": "pg_dump", "format": "custom", **(metadata or {})})


def restore_postgres_backup(*, pg_dump: str, pg_restore: str, psql: str, database_url: str, encrypted_backup: Path, safety_output: Path, secret: str) -> Path:
    database_url = libpq_url(database_url)
    """Restore a verified Lovely Tech encrypted custom-format dump.

    This is intentionally an explicit operator action. A safety backup is created
    and verified before pg_restore is allowed to replace the database.
    """
    if not encrypted_backup.exists():
        raise BackupError("Backup file not found")
    meta, raw_dump = decrypt_backup(encrypted_backup.read_bytes(), secret=secret)
    if meta.get("format") != "LTPOS-BACKUP-V1" or meta.get("format") is None:
        raise BackupError("Unsupported backup envelope")
    safety_output = Path(safety_output)
    safety_output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        safety_raw=Path(td)/"safety.dump"
        subprocess.run([pg_dump,"--format=custom","--no-owner","--no-privileges","--file",str(safety_raw),database_url],env=os.environ.copy(),check=True,capture_output=True,text=True,timeout=300)
        write_verified_backup(safety_raw.read_bytes(),safety_output,secret=secret,metadata={"source":"pre_restore_safety_backup","format":"custom"})
        restore_raw=Path(td)/"restore.dump"; restore_raw.write_bytes(raw_dump)
        subprocess.run([pg_restore,"--clean","--if-exists","--no-owner","--no-privileges","--exit-on-error","--dbname",database_url,str(restore_raw)],env=os.environ.copy(),check=True,capture_output=True,text=True,timeout=900)
        subprocess.run([psql,"--dbname",database_url,"--command","SELECT 1;"],env=os.environ.copy(),check=True,capture_output=True,text=True,timeout=60)
    return safety_output


def sync_backup_to_google_drive(*, rclone_bin: str, remote: str, remote_path: str, local_file: Path) -> str:
    if not remote:
        raise BackupError('Google Drive rclone remote is not configured')
    if not local_file.exists():
        raise BackupError('Local verified backup file not found')
    target=f"{remote.rstrip(':')}:{remote_path.strip('/')}/"
    subprocess.run([rclone_bin,'copyto',str(local_file),f"{target}{local_file.name}",'--immutable'],check=True,capture_output=True,text=True,timeout=300)
    check=subprocess.run([rclone_bin,'lsl',f"{target}{local_file.name}"],check=True,capture_output=True,text=True,timeout=60)
    if local_file.name not in check.stdout:
        raise BackupError('Google Drive verification failed')
    return f"{target}{local_file.name}"
