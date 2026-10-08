from pathlib import Path

import pytest

from app.backup.service import write_verified_backup
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
