"""Delete leftover TEST_* users (never ADMIN accounts).

Safe by default:
  * dry-run unless --apply is passed
  * refuses to continue when fewer than 10 users would remain
  * refuses a non-test database unless --allow-non-test is passed
  * never deletes users whose role is ADMIN
  * one transaction: any failure rolls everything back

Usage (run from the repo root or the backend directory):
  python scripts/cleanup_test_users.py
  python scripts/cleanup_test_users.py --apply
  python scripts/cleanup_test_users.py --apply --yes

The script reads DATABASE_URL from backend/.env (or LTPOS_ENV_FILE).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / 'backend'

MIN_USERS_REMAINING = 10
TEST_PREFIX = 'TEST_'
TEST_LIKE = r'TEST\_%'


def load_database_url() -> str:
    sys.path.insert(0, str(BACKEND_DIR))
    env_file = Path(os.environ.get('LTPOS_ENV_FILE', BACKEND_DIR / '.env'))
    os.environ.setdefault('LTPOS_ENV_FILE', str(env_file))
    from app.core.config import settings

    url = settings.database_url.strip()
    if url.startswith('postgresql+psycopg://'):
        url = 'postgresql://' + url[len('postgresql+psycopg://'):]
    return url


def database_name(url: str) -> str:
    return urlsplit(url).path.lstrip('/') or '(unknown)'


def main() -> int:
    parser = argparse.ArgumentParser(description='Delete TEST_* non-admin users.')
    parser.add_argument('--apply', action='store_true', help='Actually delete rows (default is dry-run).')
    parser.add_argument('--yes', action='store_true', help='Skip the interactive confirmation with --apply.')
    parser.add_argument('--allow-non-test', action='store_true', help='Allow running against a database whose name does not contain "test".')
    parser.add_argument('--database-url', help='Override DATABASE_URL for this run.')
    args = parser.parse_args()

    url = args.database_url or load_database_url()
    db_name = database_name(url)

    print(f'Database: {db_name}')
    print(f'Mode: {"APPLY (delete)" if args.apply else "DRY RUN (no changes)"}')

    if 'test' not in db_name.lower() and not args.allow_non_test:
        print('Refusing to run: database name does not contain "test".')
        print('Pass --allow-non-test only after confirming this database holds no live data.')
        return 2

    import psycopg

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM users')
            total_before = int(cur.fetchone()[0])

            cur.execute(
                """
                SELECT u.username, r.code
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE u.username LIKE %s ESCAPE '\\'
                  AND upper(r.code) <> 'ADMIN'
                ORDER BY u.username
                """,
                (TEST_LIKE,),
            )
            candidates = cur.fetchall()

            cur.execute(
                """
                SELECT count(*)
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE u.username LIKE %s ESCAPE '\\'
                  AND upper(r.code) = 'ADMIN'
                """,
                (TEST_LIKE,),
            )
            protected_admins = int(cur.fetchone()[0])

            to_delete = len(candidates)
            remaining = total_before - to_delete

            print(f'Users before: {total_before}')
            print(f'TEST_* users to delete (non-ADMIN): {to_delete}')
            print(f'TEST_* ADMIN users kept: {protected_admins}')
            print(f'Users remaining after delete: {remaining}')

            if not candidates:
                print('Nothing to do.')
                conn.rollback()
                return 0

            for username, role in candidates[:10]:
                print(f'  - {username} ({role})')
            if to_delete > 10:
                print(f'  ... and {to_delete - 10} more')

            if remaining < MIN_USERS_REMAINING:
                print(f'Refusing to delete: fewer than {MIN_USERS_REMAINING} users would remain.')
                conn.rollback()
                return 3

            if not args.apply:
                print('Dry run complete. Re-run with --apply to delete.')
                conn.rollback()
                return 0

            if not args.yes:
                answer = input(f'Delete {to_delete} user(s)? Type DELETE to continue: ').strip()
                if answer != 'DELETE':
                    print('Cancelled. No changes made.')
                    conn.rollback()
                    return 1

            cur.execute(
                """
                DELETE FROM users u
                USING roles r
                WHERE u.role_id = r.id
                  AND u.username LIKE %s ESCAPE '\\'
                  AND upper(r.code) <> 'ADMIN'
                """,
                (TEST_LIKE,),
            )
            deleted = cur.rowcount

            cur.execute('SELECT count(*) FROM users')
            total_after = int(cur.fetchone()[0])

            conn.commit()

            print(f'Deleted: {deleted}')
            print(f'Users after: {total_after}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
