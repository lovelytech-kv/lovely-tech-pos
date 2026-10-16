import json
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.backup.service as backup_service
import app.api.routes.backup as backup_route_module
import app.core.config as config
from app.backup.service import BackupError, restore_postgres_backup, write_verified_backup
from app.core.restore_state import (
    RestoreState,
    RestoreStateError,
    read_restore_state,
    restore_journal_path,
    restore_state_path,
    write_restore_state,
)
from app.models.shop_identity import ShopIdentity
import importlib.util

spec = importlib.util.spec_from_file_location("restore_runner", Path(__file__).parents[2] / "scripts" / "postgres_restore_runner.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
run_restore = module.run_restore


def _write_ready_state(backup_root):
    write_restore_state(
        restore_state_path(backup_root), state=RestoreState.READY, phase="TEST"
    )


def _call_api_restore(monkeypatch, backup_root, backup):
    point = SimpleNamespace(
        id=uuid.uuid4(),
        state="VERIFIED",
        storage_target=str(backup.parent),
        filename=backup.name,
    )

    class FakeSession:
        def scalar(self, *_args, **_kwargs):
            return point

        def add(self, _value):
            pass

        def commit(self):
            pass

        def close(self):
            pass

        def get_bind(self):
            class FakeEngine:
                def dispose(self): pass
            return FakeEngine()

    monkeypatch.setattr(config.settings, "backup_root", str(backup_root))
    monkeypatch.setattr(config.settings, "secret_key", "secret")
    monkeypatch.setattr(
        backup_route_module, "require_admin_reauth", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        backup_route_module, "RestoreEvent", lambda **_kwargs: object()
    )
    monkeypatch.setattr(backup_route_module, "AuditLog", lambda **_kwargs: object())
    monkeypatch.setattr(
        backup_route_module,
        "restore_postgres_backup",
        lambda **_kwargs: backup_root / "safety.ltbak",
    )
    return backup_route_module.restore(
        str(point.id),
        confirm=True,
        user=SimpleNamespace(id=uuid.uuid4(), branch_id=uuid.uuid4()),
        db=FakeSession(),
    )


def test_restore_requires_explicit_confirmation(tmp_path):
    backup = tmp_path / "backup.ltbak"
    write_verified_backup(b"dump", backup, secret="secret")
    with pytest.raises(SystemExit):
        run_restore(
            pg_dump="pg_dump", pg_restore="pg_restore", database_url="postgresql://x",
            encrypted_backup=backup, safety_output=tmp_path / "safety.ltbak",
            secret="secret", confirmed=False,
        )


def test_restore_rejects_missing_backup(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_restore(
            pg_dump="pg_dump", pg_restore="pg_restore", database_url="postgresql://x",
            encrypted_backup=tmp_path / "missing.ltbak", safety_output=tmp_path / "safety.ltbak",
            secret="secret", confirmed=True,
        )


def test_restore_rejects_backup_without_shop_identity_before_subprocess(tmp_path):
    backup = tmp_path / "legacy.ltbak"
    write_verified_backup(b"dump", backup, secret="secret")

    with pytest.raises(BackupError, match="missing shop identity"):
        restore_postgres_backup(
            pg_dump="not-run-pg-dump",
            pg_restore="not-run-pg-restore",
            psql="not-run-psql",
            database_url="postgresql://x",
            encrypted_backup=backup,
            safety_output=tmp_path / "safety.ltbak",
            secret="secret",
        )


def test_restore_reconciles_matching_identity_and_records_ready_state(tmp_path, monkeypatch):
    database_path = tmp_path / "restored.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}")
    ShopIdentity.__table__.create(engine)
    expected_shop_id = uuid.uuid4()
    with Session(engine) as db:
        db.add(ShopIdentity(shop_id=expected_shop_id))
        db.commit()

    backup = tmp_path / "backup.ltbak"
    write_verified_backup(
        b"dump",
        backup,
        secret="secret",
        metadata={"shop_id": str(expected_shop_id)},
    )
    control_root = tmp_path / "control"
    monkeypatch.setattr(config.settings, "backup_root", str(control_root))
    _write_ready_state(control_root)
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        if "--file" in command:
            Path(command[command.index("--file") + 1]).write_bytes(b"safety")

    monkeypatch.setattr(backup_service.subprocess, "run", fake_run)
    result = run_restore(
        pg_dump="pg_dump",
        pg_restore="pg_restore",
        psql="psql",
        database_url=f"sqlite:///{database_path}",
        encrypted_backup=backup,
        safety_output=tmp_path / "safety.ltbak",
        secret="secret",
        confirmed=True,
    )

    state = read_restore_state(restore_state_path(tmp_path / "control"))
    assert result == tmp_path / "safety.ltbak"
    assert state.state is RestoreState.READY
    assert state.expected_shop_id is None
    assert state.actual_shop_id is None
    assert [command[0] for command in calls] == ["pg_dump", "pg_restore", "psql"]
    journal = [
        json.loads(line)
        for line in restore_journal_path(control_root).read_text(encoding="utf-8").splitlines()
    ]
    assert journal[-1]["event"] == "RECONCILIATION_SUCCEEDED"
    engine.dispose()


def test_restore_mismatched_identity_requires_recovery_before_success(tmp_path, monkeypatch):
    database_path = tmp_path / "wrong-shop.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}")
    ShopIdentity.__table__.create(engine)
    restored_shop_id = uuid.uuid4()
    expected_shop_id = uuid.uuid4()
    with Session(engine) as db:
        db.add(ShopIdentity(shop_id=restored_shop_id))
        db.commit()

    backup = tmp_path / "backup.ltbak"
    write_verified_backup(
        b"dump",
        backup,
        secret="secret",
        metadata={"shop_id": str(expected_shop_id)},
    )
    control_root = tmp_path / "control"
    monkeypatch.setattr(config.settings, "backup_root", str(control_root))
    _write_ready_state(control_root)
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        if "--file" in command:
            Path(command[command.index("--file") + 1]).write_bytes(b"safety")

    monkeypatch.setattr(backup_service.subprocess, "run", fake_run)
    with pytest.raises(BackupError, match="does not match"):
        run_restore(
            pg_dump="pg_dump",
            pg_restore="pg_restore",
            psql="psql",
            database_url=f"sqlite:///{database_path}",
            encrypted_backup=backup,
            safety_output=tmp_path / "safety.ltbak",
            secret="secret",
            confirmed=True,
        )

    state = read_restore_state(restore_state_path(tmp_path / "control"))
    assert state.state is RestoreState.RECOVERY_REQUIRED
    assert state.expected_shop_id == expected_shop_id
    assert state.actual_shop_id is None
    assert [command[0] for command in calls] == ["pg_dump", "pg_restore"]
    engine.dispose()


def test_safety_output_outside_backup_root_uses_canonical_interlock_root(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "restored.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}")
    ShopIdentity.__table__.create(engine)
    expected_shop_id = uuid.uuid4()
    with Session(engine) as db:
        db.add(ShopIdentity(shop_id=expected_shop_id))
        db.commit()

    control_root = tmp_path / "control"
    outside_root = tmp_path / "outside"
    monkeypatch.setattr(config.settings, "backup_root", str(control_root))
    backup = tmp_path / "backup.ltbak"
    write_verified_backup(
        b"dump", backup, secret="secret", metadata={"shop_id": str(expected_shop_id)}
    )
    _write_ready_state(control_root)

    def fake_run(command, **_kwargs):
        if "--file" in command:
            Path(command[command.index("--file") + 1]).write_bytes(b"safety")

    monkeypatch.setattr(backup_service.subprocess, "run", fake_run)
    result = run_restore(
        pg_dump="pg_dump",
        pg_restore="pg_restore",
        psql="psql",
        database_url=f"sqlite:///{database_path}",
        encrypted_backup=backup,
        safety_output=outside_root / "safety.ltbak",
        secret="secret",
        confirmed=True,
    )

    assert result == outside_root / "safety.ltbak"
    assert restore_state_path(control_root).exists()
    assert not restore_state_path(outside_root).exists()
    assert not (outside_root / "restore-interlock.lock").exists()
    assert restore_journal_path(control_root).exists()
    assert not restore_journal_path(outside_root).exists()
    engine.dispose()


@pytest.mark.parametrize("state_kind", ["missing", "in_progress"])
def test_standalone_restore_requires_existing_ready_state(tmp_path, monkeypatch, state_kind):
    control_root = tmp_path / "control"
    monkeypatch.setattr(config.settings, "backup_root", str(control_root))
    backup = tmp_path / "backup.ltbak"
    expected_shop_id = uuid.uuid4()
    write_verified_backup(
        b"dump", backup, secret="secret", metadata={"shop_id": str(expected_shop_id)}
    )
    state_path = restore_state_path(control_root)
    if state_kind == "in_progress":
        write_restore_state(
            state_path,
            state=RestoreState.RESTORE_IN_PROGRESS,
            phase="BEFORE_REPLACEMENT",
            operation_id=uuid.uuid4(),
            expected_shop_id=expected_shop_id,
        )

    with pytest.raises(RestoreStateError):
        run_restore(
            pg_dump="unused",
            pg_restore="unused",
            database_url="sqlite:///:memory:",
            encrypted_backup=backup,
            safety_output=tmp_path / "safety.ltbak",
            secret="secret",
            confirmed=True,
        )

    assert state_path.exists() is (state_kind == "in_progress")
    if state_kind == "in_progress":
        assert read_restore_state(state_path).state is RestoreState.RESTORE_IN_PROGRESS


@pytest.mark.parametrize(
    ("state_kind", "expected_status"), [("missing", 503), ("in_progress", 409)]
)
def test_api_restore_requires_existing_ready_state(
    tmp_path, monkeypatch, state_kind, expected_status
):
    control_root = tmp_path / "control"
    backup = tmp_path / "backup.ltbak"
    expected_shop_id = uuid.uuid4()
    write_verified_backup(
        b"dump", backup, secret="secret", metadata={"shop_id": str(expected_shop_id)}
    )
    state_path = restore_state_path(control_root)
    if state_kind == "in_progress":
        write_restore_state(
            state_path,
            state=RestoreState.RESTORE_IN_PROGRESS,
            phase="BEFORE_REPLACEMENT",
            operation_id=uuid.uuid4(),
            expected_shop_id=expected_shop_id,
        )

    with pytest.raises(HTTPException) as error:
        _call_api_restore(monkeypatch, control_root, backup)

    assert error.value.status_code == expected_status
    assert state_path.exists() is (state_kind == "in_progress")
    if state_kind == "in_progress":
        assert read_restore_state(state_path).state is RestoreState.RESTORE_IN_PROGRESS


@pytest.mark.parametrize("entrypoint", ["standalone", "api"])
def test_ready_write_failure_never_journals_restore_success(
    tmp_path, monkeypatch, entrypoint
):
    control_root = tmp_path / "control"
    backup = tmp_path / "backup.ltbak"
    expected_shop_id = uuid.uuid4()
    write_verified_backup(
        b"dump", backup, secret="secret", metadata={"shop_id": str(expected_shop_id)}
    )
    monkeypatch.setattr(config.settings, "backup_root", str(control_root))
    _write_ready_state(control_root)

    if entrypoint == "standalone":
        original_write = module.write_restore_state

        def fail_ready_write(path, **kwargs):
            if kwargs.get("state") is RestoreState.READY:
                raise OSError("synthetic READY persistence failure")
            return original_write(path, **kwargs)

        monkeypatch.setattr(module, "write_restore_state", fail_ready_write)
        monkeypatch.setattr(
            module,
            "restore_postgres_backup",
            lambda **_kwargs: tmp_path / "safety.ltbak",
        )
        with pytest.raises(OSError, match="READY persistence failure"):
            run_restore(
                pg_dump="unused",
                pg_restore="unused",
                database_url="sqlite:///:memory:",
                encrypted_backup=backup,
                safety_output=tmp_path / "safety.ltbak",
                secret="secret",
                confirmed=True,
            )
    else:
        original_write = backup_route_module.write_restore_state

        def fail_ready_write(path, **kwargs):
            if kwargs.get("state") is RestoreState.READY:
                raise OSError("synthetic READY persistence failure")
            return original_write(path, **kwargs)

        monkeypatch.setattr(backup_route_module, "write_restore_state", fail_ready_write)
        with pytest.raises(HTTPException) as error:
            _call_api_restore(monkeypatch, control_root, backup)
        assert error.value.status_code == 500

    journal_path = restore_journal_path(control_root)
    events = [
        json.loads(line)["event"]
        for line in journal_path.read_text(encoding="utf-8").splitlines()
    ]
    assert "RECONCILIATION_SUCCEEDED" not in events
    assert events[-1] == "RESTORE_FAILED"
    assert read_restore_state(restore_state_path(control_root)).state is RestoreState.RECOVERY_REQUIRED
