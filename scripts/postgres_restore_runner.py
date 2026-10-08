from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

from app.backup.service import libpq_url, decrypt_backup, write_verified_backup


def run_restore(*, pg_dump: str, pg_restore: str, psql: str = "psql", database_url: str, encrypted_backup: Path,
                safety_output: Path, secret: str, confirmed: bool) -> Path:
    database_url = libpq_url(database_url)
    if not confirmed:
        raise SystemExit("Refusing restore: pass --confirm to acknowledge database replacement")
    if not encrypted_backup.exists():
        raise FileNotFoundError(encrypted_backup)

    blob = encrypted_backup.read_bytes()
    meta, raw_dump = decrypt_backup(blob, secret=secret)
    if meta.get("format") != "LTPOS-BACKUP-V1":
        raise ValueError("Unsupported Lovely Tech backup envelope")

    safety_output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        safety_raw = Path(td) / "safety.dump"
        subprocess.run(
            [pg_dump, "--format=custom", "--no-owner", "--no-privileges", "--file", str(safety_raw), database_url],
            env=os.environ.copy(), check=True, capture_output=True, text=True, timeout=300,
        )
        write_verified_backup(
            safety_raw.read_bytes(), safety_output, secret=secret,
            metadata={"source": "pre_restore_safety_backup", "format": "custom"},
        )

        restore_raw = Path(td) / "restore.dump"
        restore_raw.write_bytes(raw_dump)
        subprocess.run(
            [pg_restore, "--clean", "--if-exists", "--no-owner", "--no-privileges", "--exit-on-error", "--dbname", database_url, str(restore_raw)],
            env=os.environ.copy(), check=True, capture_output=True, text=True, timeout=900,
        )
        # Lightweight post-restore integrity/connectivity check.
        subprocess.run([psql, "--dbname", database_url, "--command", "SELECT 1;"], env=os.environ.copy(), check=True, capture_output=True, text=True, timeout=60)
    return safety_output


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
