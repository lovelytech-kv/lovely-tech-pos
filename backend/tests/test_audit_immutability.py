"""Real-PostgreSQL tests for migration 0030_audit_immutability.

Verifies DB-level append-only protection on audit_log, document_events,
record_versions, login_events, restore_events, idempotency_keys and
admin_recovery_codes, including the legitimate completion transitions on
idempotency_keys (response_json/completed_at) and admin_recovery_codes
(used_at/used_by). All writes happen inside a transaction that is rolled
back, so no test rows persist and no existing records are touched.
"""

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.core.config import settings

UNCONDITIONAL_TABLES = ("audit_log", "document_events", "record_versions", "login_events", "restore_events")
CONDITIONAL_TABLES = ("idempotency_keys", "admin_recovery_codes")
ALL_TABLES = UNCONDITIONAL_TABLES + CONDITIONAL_TABLES

engine = create_engine(settings.database_url)


def _utcnow():
    return datetime.now(timezone.utc)


def _first_user_id(conn):
    """Return an existing user id, or create a throwaway user inside the caller's
    (rolled-back) transaction so the tests also pass on a freshly migrated, empty DB."""
    existing = conn.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1")).scalar()
    if existing is not None:
        return existing
    now = _utcnow()
    role_id, branch_id, user_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    conn.execute(text(
        "INSERT INTO roles (id, code, name, is_system, created_at, updated_at) "
        "VALUES (:id, :code, 'LT Test Role', false, :ts, :ts)"
    ), {"id": role_id, "code": f"LT_{role_id.hex[:10]}", "ts": now})
    conn.execute(text(
        "INSERT INTO branches (id, code, name, is_active, created_at, updated_at) "
        "VALUES (:id, :code, 'LT Test Branch', true, :ts, :ts)"
    ), {"id": branch_id, "code": f"LT{branch_id.hex[:10]}", "ts": now})
    conn.execute(text(
        "INSERT INTO users (id, username, password_hash, display_name, role_id, branch_id, created_at, updated_at) "
        "VALUES (:id, :name, 'x', 'LT Test User', :role, :branch, :ts, :ts)"
    ), {"id": user_id, "name": f"lt_{user_id.hex[:10]}", "role": role_id, "branch": branch_id, "ts": now})
    return user_id


def _insert_row(conn, table, row_id, user_id, now):
    if table == "audit_log":
        conn.execute(text(
            "INSERT INTO audit_log (id, action_type, entity_type, timestamp) "
            "VALUES (:id, 'LT_TEST', 'LT_TEST', :ts)"
        ), {"id": row_id, "ts": now})
    elif table == "document_events":
        conn.execute(text(
            "INSERT INTO document_events (id, document_type, document_id, event_type, occurred_at) "
            "VALUES (:id, 'LT_TEST', :doc, 'LT_TEST', :ts)"
        ), {"id": row_id, "doc": uuid.uuid4(), "ts": now})
    elif table == "record_versions":
        conn.execute(text(
            "INSERT INTO record_versions (id, entity_type, entity_id, version, changed_at) "
            "VALUES (:id, 'LT_TEST', :ent, 1, :ts)"
        ), {"id": row_id, "ent": uuid.uuid4(), "ts": now})
    elif table == "login_events":
        conn.execute(text(
            "INSERT INTO login_events (id, username_attempted, event_type, occurred_at) "
            "VALUES (:id, 'lt_test', 'LT_TEST', :ts)"
        ), {"id": row_id, "ts": now})
    elif table == "restore_events":
        conn.execute(text(
            "INSERT INTO restore_events (id, created_at, updated_at, status) "
            "VALUES (:id, :ts, :ts, 'LT_TEST')"
        ), {"id": row_id, "ts": now})
    elif table == "idempotency_keys":
        conn.execute(text(
            "INSERT INTO idempotency_keys (id, key, request_hash, created_at) "
            "VALUES (:id, :key, :hash, :ts)"
        ), {"id": row_id, "key": f"lt-test-{row_id}", "hash": hashlib.sha256(row_id.bytes).hexdigest(), "ts": now})
    elif table == "admin_recovery_codes":
        conn.execute(text(
            "INSERT INTO admin_recovery_codes (id, code_hash, created_at, created_by) "
            "VALUES (:id, :hash, :ts, :user)"
        ), {"id": row_id, "hash": hashlib.sha256(row_id.bytes).hexdigest(), "ts": now, "user": user_id})
    else:
        raise AssertionError(f"unknown table {table}")


def _immutable_update_sql(table):
    return {
        "audit_log": "UPDATE audit_log SET reason = 'LT_TEST_CHANGED' WHERE id = :id",
        "document_events": "UPDATE document_events SET reason = 'LT_TEST_CHANGED' WHERE id = :id",
        "record_versions": "UPDATE record_versions SET version = version + 1 WHERE id = :id",
        "login_events": "UPDATE login_events SET username_attempted = 'lt_test_changed' WHERE id = :id",
        "restore_events": "UPDATE restore_events SET status = 'LT_TEST_CHANGED' WHERE id = :id",
        "idempotency_keys": "UPDATE idempotency_keys SET request_hash = 'lt-test-changed' WHERE id = :id",
        "admin_recovery_codes": "UPDATE admin_recovery_codes SET code_hash = 'lt-test-changed' WHERE id = :id",
    }[table]


def test_append_only_triggers_are_installed():
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT event_object_table, trigger_name FROM information_schema.triggers "
            "WHERE trigger_name LIKE 'trg_%_append_only_update' "
            "   OR trigger_name LIKE 'trg_%_append_only_delete' "
            "ORDER BY event_object_table, trigger_name"
        )).fetchall()
    names = {(row[0], row[1]) for row in rows}
    for table in ALL_TABLES:
        assert (table, f"trg_{table}_append_only_update") in names, f"missing update trigger on {table}"
        assert (table, f"trg_{table}_append_only_delete") in names, f"missing delete trigger on {table}"


def test_append_only_rows_reject_update_and_delete():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            user_id = _first_user_id(conn)
            assert user_id is not None, "test requires at least one existing users row"
            now = _utcnow()
            for table in ALL_TABLES:
                row_id = uuid.uuid4()
                _insert_row(conn, table, row_id, user_id, now)

                nested = conn.begin_nested()
                try:
                    conn.execute(text(_immutable_update_sql(table)), {"id": row_id})
                except DBAPIError as exc:
                    assert "append-only" in str(exc), str(exc)
                else:
                    raise AssertionError(f"{table}: UPDATE of an immutable field must be rejected")
                finally:
                    nested.rollback()

                nested = conn.begin_nested()
                try:
                    conn.execute(text(f"DELETE FROM {table} WHERE id = :id"), {"id": row_id})
                except DBAPIError as exc:
                    assert "append-only" in str(exc), str(exc)
                else:
                    raise AssertionError(f"{table}: DELETE must be rejected")
                finally:
                    nested.rollback()
        finally:
            trans.rollback()


def test_idempotency_completion_update_remains_allowed():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            now = _utcnow()
            row_id = uuid.uuid4()
            conn.execute(text(
                "INSERT INTO idempotency_keys (id, key, request_hash, created_at) "
                "VALUES (:id, :key, :hash, :ts)"
            ), {"id": row_id, "key": f"lt-test-{row_id}", "hash": hashlib.sha256(row_id.bytes).hexdigest(), "ts": now})
            conn.execute(text(
                "UPDATE idempotency_keys SET response_json = CAST(:resp AS json), completed_at = :done WHERE id = :id"
            ), {"resp": '{"status": "ok"}', "done": _utcnow(), "id": row_id})
            row = conn.execute(text(
                "SELECT completed_at FROM idempotency_keys WHERE id = :id"
            ), {"id": row_id}).one()
            assert row[0] is not None
        finally:
            trans.rollback()


def test_admin_recovery_code_use_update_remains_allowed():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            user_id = _first_user_id(conn)
            assert user_id is not None, "test requires at least one existing users row"
            now = _utcnow()
            row_id = uuid.uuid4()
            conn.execute(text(
                "INSERT INTO admin_recovery_codes (id, code_hash, created_at, created_by) "
                "VALUES (:id, :hash, :ts, :user)"
            ), {"id": row_id, "hash": hashlib.sha256(row_id.bytes).hexdigest(), "ts": now, "user": user_id})
            conn.execute(text(
                "UPDATE admin_recovery_codes SET used_at = :used, used_by = :user WHERE id = :id"
            ), {"used": _utcnow(), "user": user_id, "id": row_id})
            row = conn.execute(text(
                "SELECT used_at, used_by FROM admin_recovery_codes WHERE id = :id"
            ), {"id": row_id}).one()
            assert row[0] is not None
            assert row[1] == user_id
        finally:
            trans.rollback()
