"""Protect audit log from normal DB updates/deletes."""
from alembic import op

revision = "0014_audit_immutability"
down_revision = "0013_locked_completion_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION ltpos_audit_immutable() RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'audit_log is append-only';
    END;
    $$ LANGUAGE plpgsql;
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_audit_immutable_update ON audit_log")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_immutable_delete ON audit_log")
    op.execute("CREATE TRIGGER trg_audit_immutable_update BEFORE UPDATE ON audit_log FOR EACH ROW EXECUTE FUNCTION ltpos_audit_immutable()")
    op.execute("CREATE TRIGGER trg_audit_immutable_delete BEFORE DELETE ON audit_log FOR EACH ROW EXECUTE FUNCTION ltpos_audit_immutable()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_immutable_update ON audit_log")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_immutable_delete ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS ltpos_audit_immutable()")
