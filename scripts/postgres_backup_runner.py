from __future__ import annotations
import argparse, os, subprocess, tempfile
from pathlib import Path
from app.backup.service import libpq_url, write_verified_backup, decrypt_backup

def run_dump(*, pg_dump: str, database_url: str, output: Path, secret: str) -> Path:
    database_url = libpq_url(database_url)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "database.dump"
        env = os.environ.copy()
        cmd = [pg_dump, "--format=custom", "--no-owner", "--no-privileges", "--file", str(raw), database_url]
        subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
        payload = raw.read_bytes()
        result = write_verified_backup(payload, output, secret=secret, metadata={"source":"pg_dump","format":"custom"})
        decrypt_backup(result.read_bytes(), secret=secret)
        return result

def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--pg-dump", default="pg_dump")
    p.add_argument("--database-url", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--secret", default=os.environ.get("SECRET_KEY"))
    a=p.parse_args()
    print(run_dump(pg_dump=a.pg_dump,database_url=a.database_url,output=Path(a.output),secret=a.secret))
if __name__ == "__main__": main()
