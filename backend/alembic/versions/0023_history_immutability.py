"""Protect historical/audit-style records from UPDATE/DELETE at DB level."""
from alembic import op

revision = "0023_history_immutability"
down_revision = "0022_payment_idempotency"
branch_labels = None
depends_on = None

TABLES = ("target_progress_snapshots", "record_versions", "document_events", "login_events")


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION ltpos_history_immutable() RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'historical record is append-only: %', TG_TABLE_NAME;
    END;
    $$ LANGUAGE plpgsql;
    """)
    for table in TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable_update ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable_delete ON {table}")
        op.execute(f"CREATE TRIGGER trg_{table}_immutable_update BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION ltpos_history_immutable()")
        op.execute(f"CREATE TRIGGER trg_{table}_immutable_delete BEFORE DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION ltpos_history_immutable()")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable_update ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable_delete ON {table}")
    op.execute("DROP FUNCTION IF EXISTS ltpos_history_immutable()")
