"""Enforce one reload entry per open business day.

Existing duplicate historical rows are preserved. The trigger blocks future
duplicates while DayFinanceService row-locks the day session for concurrency.
"""
from alembic import op

revision = "0024_reload_once_per_day"
down_revision = "0023_history_immutability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION ltpos_reload_once_per_day() RETURNS trigger AS $$
    BEGIN
      IF EXISTS (
        SELECT 1 FROM reload_entries
        WHERE day_session_id = NEW.day_session_id
          AND id <> NEW.id
      ) THEN
        RAISE EXCEPTION 'reload already entered for this business day';
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_reload_once_per_day ON reload_entries")
    op.execute("""
    CREATE TRIGGER trg_reload_once_per_day
    BEFORE INSERT OR UPDATE ON reload_entries
    FOR EACH ROW EXECUTE FUNCTION ltpos_reload_once_per_day()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_reload_once_per_day ON reload_entries")
    op.execute("DROP FUNCTION IF EXISTS ltpos_reload_once_per_day")
