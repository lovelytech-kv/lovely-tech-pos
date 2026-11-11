"""Backup import metadata

Revision ID: 0043_backup_import
Revises: 0042_machine_join_audit
Create Date: 2026-11-11
"""
from alembic import op

revision = "0043_backup_import"
down_revision = "0042_machine_join_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE backup_points ADD COLUMN IF NOT EXISTS imported_at TIMESTAMPTZ")
    op.execute("ALTER TABLE backup_points ADD COLUMN IF NOT EXISTS imported_by UUID")
    op.execute("ALTER TABLE backup_points ADD COLUMN IF NOT EXISTS source_filename VARCHAR(300)")
    op.execute("ALTER TABLE backup_points ADD COLUMN IF NOT EXISTS source_metadata JSONB")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_backup_points_imported_by'
            ) THEN
                ALTER TABLE backup_points
                ADD CONSTRAINT fk_backup_points_imported_by
                FOREIGN KEY (imported_by) REFERENCES users(id) ON DELETE RESTRICT;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE backup_points DROP CONSTRAINT IF EXISTS fk_backup_points_imported_by")
    op.execute("ALTER TABLE backup_points DROP COLUMN IF EXISTS source_metadata")
    op.execute("ALTER TABLE backup_points DROP COLUMN IF EXISTS source_filename")
    op.execute("ALTER TABLE backup_points DROP COLUMN IF EXISTS imported_by")
    op.execute("ALTER TABLE backup_points DROP COLUMN IF EXISTS imported_at")