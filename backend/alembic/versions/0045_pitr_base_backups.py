"""PITR base backups metadata table

Revision ID: 0045_pitr_base_backups
Revises: 0044_shop_name_backfill
Create Date: 2026-11-15
"""
from alembic import op

revision = "0045_pitr_base_backups"
down_revision = "0044_shop_name_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS pitr_base_backups (
            id SERIAL PRIMARY KEY,
            base_path TEXT NOT NULL,
            backup_start_time TIMESTAMPTZ NOT NULL,
            backup_end_time TIMESTAMPTZ NOT NULL,
            wal_min TEXT,
            wal_max TEXT,
            size_bytes BIGINT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            created_by TEXT
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_pitr_base_backups_start_time
        ON pitr_base_backups (backup_start_time DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pitr_base_backups")
