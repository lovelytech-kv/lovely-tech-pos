"""Automatic backup for Shift End / Day End (Requirements 15).

Flow
----
* ``create_verified_backup`` is the one place that creates a backup point: dump -> encrypt ->
  decrypt-verify -> (Google Drive upload, retried) -> VERIFIED. If Drive is unreachable it falls
  back to a separate configured target (USB/external/network folder), verifies that copy and leaves
  the point ``PENDING_SYNC`` so it uploads automatically once the network is back.
* ``ensure_close_backup`` is called by the Shift End / Day End endpoints. A verified backup newer
  than ``backup_close_reuse_seconds`` lets the close proceed. Otherwise a background job takes the
  backup with automatic retries (exponential back-off) and the endpoint answers "running" so the
  client simply asks again; the close completes only after a backup is verified. The job never
  reports success unless a backup point is VERIFIED, and a failed job changes nothing.
* ``sync_pending_backups`` is the queued Google Drive upload that retries in the background.
"""
from __future__ import annotations

import logging
import re
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backup.service import BackupError, create_postgres_dump, decrypt_backup, sync_backup_to_google_drive
from app.core.config import settings as default_settings
from app.db.session import get_session_factory
from app.models.backup import BackupPoint
from app.models.security import AuditLog

log = logging.getLogger(__name__)

MIN_REUSE_SECONDS = 30  # the client re-asks every few seconds; the window must outlive that hand-off


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_filename(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return safe if safe.lower().endswith(".ltbak") else safe + ".ltbak"


def _redact(message: str, cfg) -> str:
    """Never persist/return the DB password or the encryption secret (pg_dump errors echo the URL)."""
    from sqlalchemy.engine import make_url
    from app.backup.service import libpq_url
    secrets = [cfg.database_url, libpq_url(cfg.database_url)]
    try:
        password = make_url(cfg.database_url).password
        if password:
            secrets.append(password)
    except Exception:
        pass
    secrets.append(cfg.secret_key)
    for secret in sorted({x for x in secrets if x and len(x) >= 4}, key=len, reverse=True):
        message = message.replace(secret, "***")
    return message


def _describe(exc: Exception, cfg) -> str:
    message = str(exc)
    stderr = getattr(exc, "stderr", None)
    if stderr:
        message += f" | {str(stderr).strip()[-500:]}"
    return _redact(message, cfg)


def create_verified_backup(
    db: Session, *, branch_id, user_id, filename: str, cfg=None, upload_attempts: int = 1,
    dump_fn: Callable = create_postgres_dump, sync_fn: Callable = sync_backup_to_google_drive,
    sleep: Callable[[float], None] = time.sleep,
) -> BackupPoint:
    """Create, verify and (when configured) upload one backup. Raises BackupError on failure."""
    cfg = cfg or default_settings
    safe_name = _safe_filename(filename)
    root = Path(cfg.backup_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    dest = (root / safe_name).resolve()
    if root not in dest.parents:
        raise BackupError("Invalid backup filename")
    point = BackupPoint(branch_id=branch_id, state="CREATING", storage_target=str(root), filename=safe_name, created_by=user_id)
    db.add(point)
    db.commit()  # persist the CREATING row so a failure can always be recorded against it
    point_id = point.id
    try:
        blob = dump_fn(pg_dump=cfg.pg_dump_bin, database_url=cfg.database_url, destination=dest,
                       secret=cfg.secret_key, metadata={"backup_point_id": str(point.id)})
        meta, _ = decrypt_backup(Path(blob).read_bytes(), secret=cfg.secret_key)
        point.state = "VERIFIED"
        point.sha256 = meta["sha256"]
        point.verified_at = _now()
        if cfg.google_drive_rclone_remote:
            last_exc: Exception | None = None
            for attempt in range(1, max(1, upload_attempts) + 1):
                try:
                    point.remote_path = sync_fn(rclone_bin=cfg.rclone_bin, remote=cfg.google_drive_rclone_remote,
                                                remote_path=cfg.google_drive_backup_path, local_file=dest)
                    point.sync_state = "SYNCED"
                    last_exc = None
                    break
                except Exception as exc:  # network down, rclone missing, quota ...
                    last_exc = exc
                    if attempt < upload_attempts:
                        sleep(min(5 * attempt, 15))
            if last_exc is not None:
                point.sync_state = "PENDING_SYNC"
                note = f"Local backup verified; Google Drive sync pending: {_describe(last_exc, cfg)[:1200]}"
                alt = (cfg.backup_alternate_target or "").strip()
                if alt:
                    # Drive is unreachable: a verified copy on a separate target must exist before we accept.
                    alt_dir = Path(alt).resolve()
                    if alt_dir == root:
                        raise BackupError("Alternate backup target must be different from the main backup folder")
                    alt_dir.mkdir(parents=True, exist_ok=True)
                    copy = alt_dir / dest.name
                    shutil.copy2(dest, copy)
                    alt_meta, _ = decrypt_backup(copy.read_bytes(), secret=cfg.secret_key)
                    if alt_meta["sha256"] != meta["sha256"]:
                        raise BackupError("Alternate backup copy failed verification")
                    note += f" | verified copy kept on alternate target ({alt_dir.name})"
                point.failure_reason = note
        else:
            point.sync_state = "LOCAL_ONLY"
        db.add(AuditLog(branch_id=branch_id, actor_user_id=user_id, action_type="BACKUP_VERIFIED", entity_type="BACKUP_POINT",
                        entity_id=point.id, timestamp=_now(), after_json={"filename": safe_name, "sha256": point.sha256,
                                                                          "sync_state": point.sync_state},
                        source_transaction_id=point.id))
        db.commit()
        return point
    except Exception as exc:
        db.rollback()
        # A failed or unverified backup is never a restore point.
        failed = db.get(BackupPoint, point_id)
        failed.state = "FAILED"
        failed.verified_at = None
        failed.sha256 = None
        reason = _describe(exc, cfg)
        failed.failure_reason = reason[:2000]
        db.commit()
        raise BackupError(reason) from None


# --------------------------------------------------------------------------- close-time job
@dataclass
class CloseBackupJob:
    branch_id: str
    started_at: datetime
    max_attempts: int
    state: str = "RUNNING"  # RUNNING | FAILED
    attempt: int = 0
    step: str = "starting"
    last_error: str | None = None  # Admin-only detail; never returned to the cashier


@dataclass
class CloseBackupStatus:
    ready: bool
    state: str  # READY | RUNNING | FAILED
    attempt: int = 0
    max_attempts: int = 0
    step: str = ""

    def as_payload(self) -> dict:
        return {"backup_status": self.state, "attempt": self.attempt, "max_attempts": self.max_attempts, "step": self.step,
                "message": "Backup in progress. Shift/Day End completes automatically once the backup is verified."}


_JOBS: dict[str, CloseBackupJob] = {}
_LOCK = threading.Lock()


def reset_jobs() -> None:
    """Test helper."""
    with _LOCK:
        _JOBS.clear()


def latest_fresh_backup(db: Session, branch_id, within_seconds: int) -> BackupPoint | None:
    cutoff = _now() - timedelta(seconds=max(within_seconds, MIN_REUSE_SECONDS))
    return db.scalar(select(BackupPoint).where(
        BackupPoint.branch_id == branch_id, BackupPoint.state == "VERIFIED",
        BackupPoint.verified_at.is_not(None), BackupPoint.verified_at >= cutoff,
    ).order_by(BackupPoint.verified_at.desc()).limit(1))


def run_close_backup_job(job: CloseBackupJob, key: str, *, user_id, cfg=None, session_factory=None,
                         dump_fn: Callable = create_postgres_dump, sync_fn: Callable = sync_backup_to_google_drive,
                         sleep: Callable[[float], None] = time.sleep) -> None:
    """Take a backup, retrying automatically until one is verified or attempts run out."""
    cfg = cfg or default_settings
    session_factory = session_factory or get_session_factory()
    delay = 2.0
    for attempt in range(1, job.max_attempts + 1):
        job.attempt = attempt
        job.step = "creating and verifying backup"
        db = session_factory()
        try:
            create_verified_backup(db, branch_id=job.branch_id, user_id=user_id,
                                   filename=f"auto-close-{_now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}.ltbak",
                                   cfg=cfg, upload_attempts=cfg.backup_upload_attempts, dump_fn=dump_fn, sync_fn=sync_fn, sleep=sleep)
            with _LOCK:
                if _JOBS.get(key) is job:
                    del _JOBS[key]
            return
        except Exception as exc:
            job.last_error = str(exc)[:500]
            log.warning("Automatic close backup attempt %d/%d failed: %s", attempt, job.max_attempts, exc)
        finally:
            db.close()
        if attempt < job.max_attempts:
            job.step = f"retrying in {int(delay)}s"
            sleep(delay)
            delay = min(delay * 2, max(1, cfg.backup_close_retry_max_delay_seconds))
    db = session_factory()
    try:
        db.add(AuditLog(branch_id=job.branch_id, actor_user_id=user_id, action_type="BACKUP_AUTO_CLOSE_FAILED",
                        entity_type="BACKUP_POINT", timestamp=_now(),
                        after_json={"attempts": job.max_attempts, "last_error": job.last_error}))
        db.commit()
    except Exception:  # pragma: no cover - audit must not mask the failure state
        db.rollback()
    finally:
        db.close()
    job.state = "FAILED"
    job.step = "failed"


def ensure_close_backup(db: Session, *, branch_id, user_id, cfg=None, background: bool = True, **job_kwargs) -> CloseBackupStatus:
    """READY when a fresh verified backup exists; otherwise start/observe the automatic backup job."""
    cfg = cfg or default_settings
    key = str(branch_id)
    with _LOCK:
        if latest_fresh_backup(db, branch_id, cfg.backup_close_reuse_seconds) is not None:
            _JOBS.pop(key, None)
            return CloseBackupStatus(True, "READY")
        job = _JOBS.get(key)
        if job is not None and job.state == "FAILED":
            del _JOBS[key]  # report the failure once; the next request starts a fresh attempt cycle
            return CloseBackupStatus(False, "FAILED", job.attempt, job.max_attempts, job.step)
        if job is None:
            job = CloseBackupJob(branch_id=key, started_at=_now(), max_attempts=max(1, cfg.backup_close_max_attempts))
            _JOBS[key] = job
            if background:
                threading.Thread(target=run_close_backup_job, args=(job, key), kwargs={"user_id": user_id, "cfg": cfg, **job_kwargs},
                                 daemon=True, name="close-backup").start()
        return CloseBackupStatus(False, "RUNNING", job.attempt, job.max_attempts, job.step)


# --------------------------------------------------------------------------- queued Drive sync
def sync_pending_backups(db: Session, *, cfg=None, sync_fn: Callable = sync_backup_to_google_drive, limit: int = 20) -> int:
    """Upload verified-but-unsynced backups to Google Drive. Stops at the first failure (network down)."""
    cfg = cfg or default_settings
    if not cfg.google_drive_rclone_remote:
        return 0
    points = db.scalars(select(BackupPoint).where(BackupPoint.state == "VERIFIED", BackupPoint.sync_state == "PENDING_SYNC")
                        .order_by(BackupPoint.verified_at).limit(limit)).all()
    done = 0
    for point in points:
        try:
            point.remote_path = sync_fn(rclone_bin=cfg.rclone_bin, remote=cfg.google_drive_rclone_remote,
                                        remote_path=cfg.google_drive_backup_path, local_file=Path(point.storage_target) / point.filename)
            point.sync_state = "SYNCED"
            point.failure_reason = None
            db.add(AuditLog(branch_id=point.branch_id, actor_user_id=None, action_type="BACKUP_SYNCED", entity_type="BACKUP_POINT",
                            entity_id=point.id, timestamp=_now(), after_json={"remote_path": point.remote_path, "queued": True},
                            source_transaction_id=point.id))
            db.commit()
            done += 1
        except Exception as exc:
            db.rollback()
            log.info("Queued Google Drive sync still pending (%s): %s", point.filename, exc)
            break
    return done


def run_pending_sync_once(session_factory=None, cfg=None) -> int:
    db = (session_factory or get_session_factory())()
    try:
        return sync_pending_backups(db, cfg=cfg)
    except Exception as exc:  # pragma: no cover - background loop must never die
        log.warning("Queued backup sync failed: %s", exc)
        return 0
    finally:
        db.close()
