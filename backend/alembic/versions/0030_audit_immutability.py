"""Append-only DB protection for audit, history, idempotency and recovery tables.

Revision ID: 0030_audit_immutability
Revises: 0029_credit_settlement_version
"""
from alembic import op

revision = "0030_audit_immutability"
down_revision = "0029_credit_settlement_version"
branch_labels = None
depends_on = None

UNCONDITIONAL_TABLES = ("audit_log", "document_events", "record_versions", "login_events", "restore_events")
CONDITIONAL_TABLES = ("idempotency_keys", "admin_recovery_codes")
ALL_TABLES = UNCONDITIONAL_TABLES + CONDITIONAL_TABLES


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION ltpos_append_only_immutable() RETURNS trigger AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'This table is append-only and cannot be updated or deleted: %', TG_TABLE_NAME;
      END IF;
      IF TG_TABLE_NAME = 'idempotency_keys' THEN
        IF OLD.key IS DISTINCT FROM NEW.key
           OR OLD.user_id IS DISTINCT FROM NEW.user_id
           OR OLD.request_hash IS DISTINCT FROM NEW.request_hash
           OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
          RAISE EXCEPTION 'This table is append-only and cannot be updated or deleted: %', TG_TABLE_NAME;
        END IF;
        RETURN NEW;
      END IF;
      IF TG_TABLE_NAME = 'admin_recovery_codes' THEN
        IF OLD.code_hash IS DISTINCT FROM NEW.code_hash
           OR OLD.created_at IS DISTINCT FROM NEW.created_at
           OR OLD.created_by IS DISTINCT FROM NEW.created_by THEN
          RAISE EXCEPTION 'This table is append-only and cannot be updated or deleted: %', TG_TABLE_NAME;
        END IF;
        RETURN NEW;
      END IF;
      RAISE EXCEPTION 'This table is append-only and cannot be updated or deleted: %', TG_TABLE_NAME;
    END;
    $$ LANGUAGE plpgsql;
    """)
    for table in ALL_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only_update ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only_delete ON {table}")
        op.execute(f"CREATE TRIGGER trg_{table}_append_only_update BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION ltpos_append_only_immutable()")
        op.execute(f"CREATE TRIGGER trg_{table}_append_only_delete BEFORE DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION ltpos_append_only_immutable()")


def downgrade() -> None:
    for table in ALL_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only_update ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only_delete ON {table}")
    op.execute("DROP FUNCTION IF EXISTS ltpos_append_only_immutable()")
