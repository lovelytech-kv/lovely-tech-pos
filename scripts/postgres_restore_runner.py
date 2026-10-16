from __future__ import annotations

import argparse
import os
from pathlib import Path
import uuid

from app.backup.service import decrypt_backup, restore_postgres_backup, validate_backup_envelope_metadata
from app.core.config import settings
from app.core.restore_state import (
    RestoreInterlockBusy,
    RestoreState,
    RestoreStateError,
    acquire_restore_interlock,
    append_restore_journal,
    read_restore_state,
    restore_state_path,
    write_restore_state,
)


def run_restore(*, pg_dump: str, pg_restore: str, psql: str = "psql", database_url: str, encrypted_backup: Path,
                safety_output: Path, secret: str, confirmed: bool) -> Path:
    if not confirmed:
        raise SystemExit("Refusing restore: pass --confirm to acknowledge database replacement")
    if not encrypted_backup.exists():
        raise FileNotFoundError(encrypted_backup)

    blob = encrypted_backup.read_bytes()
    meta, _ = decrypt_backup(blob, secret=secret)
    expected_shop_id = validate_backup_envelope_metadata(meta)
    operation_id = uuid.uuid4()
    control_root = Path(settings.backup_root)
    state_path = restore_state_path(control_root)

    with acquire_restore_interlock(control_root):
        try:
            current = read_restore_state(state_path)
        except RestoreStateError as exc:
            raise RestoreStateError("Restore recovery state is unavailable; restore is disabled.") from exc
        if current.state is not RestoreState.READY:
            raise RestoreStateError("Restore recovery is incomplete; restore is disabled.")
        try:
            write_restore_state(
                state_path, state=RestoreState.RESTORE_IN_PROGRESS,
                phase="BEFORE_REPLACEMENT", operation_id=operation_id,
                expected_shop_id=expected_shop_id,
            )
            append_restore_journal(
                control_root,
                {"event": "RESTORE_IN_PROGRESS", "operation_id": str(operation_id),
                 "expected_shop_id": str(expected_shop_id)},
            )
            safety = restore_postgres_backup(
                pg_dump=pg_dump, pg_restore=pg_restore, psql=psql,
                database_url=database_url, encrypted_backup=encrypted_backup,
                safety_output=safety_output, secret=secret,
            )
            write_restore_state(
                state_path, state=RestoreState.READY,
                phase="RECONCILIATION_SUCCEEDED",
            )
            append_restore_journal(
                control_root,
                {"event": "RECONCILIATION_SUCCEEDED", "operation_id": str(operation_id),
                 "shop_id": str(expected_shop_id)},
            )
            return safety
        except Exception as exc:
            report_error = None
            try:
                write_restore_state(
                    state_path, state=RestoreState.RECOVERY_REQUIRED,
                    phase="FAILED", operation_id=operation_id,
                    expected_shop_id=expected_shop_id, error=str(exc)[:500],
                )
                append_restore_journal(
                    control_root,
                    {"event": "RESTORE_FAILED", "operation_id": str(operation_id),
                     "error": str(exc)[:500]},
                )
            except Exception as report_exc:
                report_error = report_exc
            if report_error is not None:
                raise RestoreStateError(
                    "Restore failed and recovery state could not be durably reported."
                ) from report_error
            raise


def main() -> None:
    p = argparse.ArgumentParser(description="Lovely Tech POS encrypted PostgreSQL restore runner")
    p.add_argument("--pg-dump", default="pg_dump")
    p.add_argument("--pg-restore", default="pg_restore")
    p.add_argument("--psql", default=os.environ.get("PSQL_BIN", "psql"))
    p.add_argument("--database-url", required=True)
    p.add_argument("--backup", required=True)
    p.add_argument("--safety-output", required=True)
    p.add_argument("--secret", default=os.environ.get("SECRET_KEY"))
    p.add_argument("--confirm", action="store_true")
    a = p.parse_args()
    safety = run_restore(
        pg_dump=a.pg_dump, pg_restore=a.pg_restore, psql=a.psql, database_url=a.database_url,
        encrypted_backup=Path(a.backup), safety_output=Path(a.safety_output),
        secret=a.secret, confirmed=a.confirm,
    )
    print(safety)


if __name__ == "__main__":
    main()
