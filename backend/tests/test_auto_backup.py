"""Automatic backup at Shift End / Day End (Requirements 15): runs real PostgreSQL rows,
fake pg_dump/rclone so failures and retries are deterministic."""
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.backup import auto
from app.backup.service import BackupError, decrypt_backup, write_verified_backup
from app.core.config import settings
from app.models.backup import BackupPoint
from app.models.master import Branch, Role, User
from app.models.security import AuditLog


def _db_available() -> bool:
    try:
        with create_engine(settings.database_url).connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(settings.database_url)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]
    with factory() as db:
        branch = Branch(code=f"AB{suffix}", name="Auto backup test", is_active=True)
        role = Role(code=f"AB_{suffix}", name="AB role", is_system=False)
        db.add_all([branch, role])
        db.flush()
        user = User(username=f"ab_{suffix}", password_hash="x", display_name="AB", role_id=role.id, branch_id=branch.id)
        db.add(user)
        db.commit()
        ids = (branch.id, user.id)
    auto.reset_jobs()
    cfg = settings.model_copy(update={"backup_root": str(tmp_path / "main"), "google_drive_rclone_remote": "",
                                      "backup_alternate_target": "", "backup_close_max_attempts": 4,
                                      "backup_close_reuse_seconds": 60, "backup_upload_attempts": 3})
    yield {"factory": factory, "branch": ids[0], "user": ids[1], "cfg": cfg, "tmp": tmp_path}
    auto.reset_jobs()
    engine.dispose()


def good_dump(*, pg_dump, database_url, destination, secret, metadata=None):
    return write_verified_backup(b"database-bytes", destination, secret=secret, metadata=metadata)


class FlakyDump:
    def __init__(self, fail_times):
        self.fail_times, self.calls = fail_times, 0

    def __call__(self, **kw):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError(f"pg_dump exploded (call {self.calls})")
        return good_dump(**kw)


def _points(env):
    with env["factory"]() as db:
        return list(db.scalars(select(BackupPoint).where(BackupPoint.branch_id == env["branch"]).order_by(BackupPoint.created_at)))


def _new_job(env, max_attempts=4):
    return auto.CloseBackupJob(branch_id=str(env["branch"]), started_at=auto._now(), max_attempts=max_attempts)


def test_job_retries_automatically_until_a_backup_is_verified(env):
    job, sleeps, dump = _new_job(env), [], FlakyDump(fail_times=2)
    auto._JOBS[str(env["branch"])] = job
    auto.run_close_backup_job(job, str(env["branch"]), user_id=env["user"], cfg=env["cfg"], session_factory=env["factory"],
                              dump_fn=dump, sleep=sleeps.append)
    states = [p.state for p in _points(env)]
    assert states == ["FAILED", "FAILED", "VERIFIED"]
    assert dump.calls == 3 and sleeps == [2.0, 4.0]  # exponential back-off between automatic retries
    assert str(env["branch"]) not in auto._JOBS  # finished jobs are removed
    failed = _points(env)[0]
    assert failed.verified_at is None and "exploded" in failed.failure_reason  # a failed backup is never a restore point


def test_job_reports_failed_after_all_attempts_and_audits_it(env):
    job = _new_job(env, max_attempts=3)
    auto._JOBS[str(env["branch"])] = job
    auto.run_close_backup_job(job, str(env["branch"]), user_id=env["user"], cfg=env["cfg"], session_factory=env["factory"],
                              dump_fn=FlakyDump(fail_times=99), sleep=lambda s: None)
    assert job.state == "FAILED" and job.attempt == 3
    assert all(p.state == "FAILED" for p in _points(env)) and len(_points(env)) == 3
    with env["factory"]() as db:
        audits = db.scalars(select(AuditLog).where(AuditLog.action_type == "BACKUP_AUTO_CLOSE_FAILED",
                                                   AuditLog.branch_id == env["branch"])).all()
    assert len(audits) == 1 and audits[0].after_json["attempts"] == 3


def test_ensure_close_backup_lifecycle(env):
    cfg, branch, user = env["cfg"], env["branch"], env["user"]
    with env["factory"]() as db:
        # No backup yet -> an automatic job is registered and the caller is told to wait.
        st = auto.ensure_close_backup(db, branch_id=branch, user_id=user, cfg=cfg, background=False)
        assert (st.ready, st.state) == (False, "RUNNING") and st.max_attempts == 4
        assert "error" not in st.as_payload() and "last_error" not in st.as_payload()
        # Asking again does not start a second job.
        assert auto.ensure_close_backup(db, branch_id=branch, user_id=user, cfg=cfg, background=False).state == "RUNNING"
        # Job exhausted its retries: failure is reported once, then a fresh cycle may start.
        auto._JOBS[str(branch)].state = "FAILED"
        assert auto.ensure_close_backup(db, branch_id=branch, user_id=user, cfg=cfg, background=False).state == "FAILED"
        assert auto.ensure_close_backup(db, branch_id=branch, user_id=user, cfg=cfg, background=False).state == "RUNNING"
        # A verified backup makes the close ready and clears the job.
        auto.create_verified_backup(db, branch_id=branch, user_id=user, filename="x.ltbak", cfg=cfg, dump_fn=good_dump)
        st = auto.ensure_close_backup(db, branch_id=branch, user_id=user, cfg=cfg, background=False)
        assert st.ready and str(branch) not in auto._JOBS


def test_stale_backup_does_not_satisfy_a_close(env):
    cfg, branch, user = env["cfg"], env["branch"], env["user"]
    with env["factory"]() as db:
        point = auto.create_verified_backup(db, branch_id=branch, user_id=user, filename="old.ltbak", cfg=cfg, dump_fn=good_dump)
        point.verified_at = auto._now() - auto.timedelta(hours=3)
        db.commit()
        assert auto.ensure_close_backup(db, branch_id=branch, user_id=user, cfg=cfg, background=False).state == "RUNNING"


def test_drive_upload_is_retried_before_giving_up(env):
    cfg = env["cfg"].model_copy(update={"google_drive_rclone_remote": "gdrive"})
    calls = []

    def flaky_sync(**kw):
        calls.append(1)
        if len(calls) < 3:
            raise BackupError("network down")
        return "gdrive:Lovely/x.ltbak"

    with env["factory"]() as db:
        p = auto.create_verified_backup(db, branch_id=env["branch"], user_id=env["user"], filename="a.ltbak", cfg=cfg,
                                        upload_attempts=3, dump_fn=good_dump, sync_fn=flaky_sync, sleep=lambda s: None)
    assert (p.state, p.sync_state, len(calls)) == ("VERIFIED", "SYNCED", 3)


def test_drive_down_falls_back_to_verified_alternate_target(env):
    alt = env["tmp"] / "usb"
    cfg = env["cfg"].model_copy(update={"google_drive_rclone_remote": "gdrive", "backup_alternate_target": str(alt)})

    def down(**kw):
        raise BackupError("no internet")

    with env["factory"]() as db:
        p = auto.create_verified_backup(db, branch_id=env["branch"], user_id=env["user"], filename="b.ltbak", cfg=cfg,
                                        upload_attempts=2, dump_fn=good_dump, sync_fn=down, sleep=lambda s: None)
    assert (p.state, p.sync_state) == ("VERIFIED", "PENDING_SYNC")  # queued for upload once the network returns
    copy = alt / "b.ltbak"
    assert copy.exists()
    decrypt_backup(copy.read_bytes(), secret=cfg.secret_key)  # the alternate copy is itself verified
    assert "alternate target" in p.failure_reason


def test_alternate_target_failure_fails_the_backup(env):
    blocker = env["tmp"] / "not-a-dir"
    blocker.write_text("file in the way")
    cfg = env["cfg"].model_copy(update={"google_drive_rclone_remote": "gdrive", "backup_alternate_target": str(blocker)})

    def down(**kw):
        raise BackupError("no internet")

    with env["factory"]() as db:
        with pytest.raises(BackupError):
            auto.create_verified_backup(db, branch_id=env["branch"], user_id=env["user"], filename="c.ltbak", cfg=cfg,
                                        upload_attempts=1, dump_fn=good_dump, sync_fn=down, sleep=lambda s: None)
    assert [p.state for p in _points(env)] == ["FAILED"]


def test_queued_pending_backups_sync_when_network_returns(env):
    cfg = env["cfg"].model_copy(update={"google_drive_rclone_remote": "gdrive"})
    with env["factory"]() as db:
        for name in ("q1.ltbak", "q2.ltbak"):
            auto.create_verified_backup(db, branch_id=env["branch"], user_id=env["user"], filename=name, cfg=cfg,
                                        upload_attempts=1, dump_fn=good_dump,
                                        sync_fn=lambda **kw: (_ for _ in ()).throw(BackupError("offline")), sleep=lambda s: None)
        assert {p.sync_state for p in _points(env)} == {"PENDING_SYNC"}
        # Still offline: nothing changes, nothing raises.
        assert auto.sync_pending_backups(db, cfg=cfg, sync_fn=lambda **kw: (_ for _ in ()).throw(BackupError("offline"))) == 0
        # Network is back (the queue is global, so leftovers from other tests may sync too).
        assert auto.sync_pending_backups(db, cfg=cfg, sync_fn=lambda **kw: f"gdrive:L/{kw['local_file'].name}") >= 2
    assert {p.sync_state for p in _points(env)} == {"SYNCED"}


def test_failure_reasons_never_contain_the_database_password_or_secret(env):
    import subprocess
    cfg = env["cfg"].model_copy(update={"database_url": "postgresql+psycopg://lovely_pos:SuperSecretPw9@127.0.0.1:5432/x"})

    def boom(*, pg_dump, database_url, destination, secret, metadata=None):
        raise subprocess.CalledProcessError(1, [pg_dump, "--file", "f", "postgresql://lovely_pos:SuperSecretPw9@127.0.0.1:5432/x"],
                                            stderr=f"connection failed for postgresql://lovely_pos:SuperSecretPw9@h/x key={cfg.secret_key}")

    with env["factory"]() as db:
        with pytest.raises(BackupError) as err:
            auto.create_verified_backup(db, branch_id=env["branch"], user_id=env["user"], filename="r.ltbak", cfg=cfg, dump_fn=boom)
    stored = _points(env)[0].failure_reason
    for text_ in (stored, str(err.value)):
        assert "SuperSecretPw9" not in text_ and cfg.secret_key not in text_ and "***" in text_
