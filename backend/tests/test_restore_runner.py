from pathlib import Path
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.backup.service as backup_service
import app.core.config as config
from app.backup.service import BackupError, restore_postgres_backup, write_verified_backup
from app.core.restore_state import RestoreState, read_restore_state, restore_state_path
from app.models.shop_identity import ShopIdentity
import importlib.util

spec = importlib.util.spec_from_file_location("restore_runner", Path(__file__).parents[2] / "scripts" / "postgres_restore_runner.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
run_restore = module.run_restore


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
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        if "--file" in command:
            Path(command[command.index("--file") + 1]).write_bytes(b"safety")

    monkeypatch.setattr(backup_service.subprocess, "run", fake_run)
    monkeypatch.setattr(config.settings, "backup_root", str(tmp_path / "control"))

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
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        if "--file" in command:
            Path(command[command.index("--file") + 1]).write_bytes(b"safety")

    monkeypatch.setattr(backup_service.subprocess, "run", fake_run)
    monkeypatch.setattr(config.settings, "backup_root", str(tmp_path / "control"))

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
    engine.dispose()
