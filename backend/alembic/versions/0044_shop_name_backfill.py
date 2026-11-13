"""Shop name backfill — sync shop_identity.shop_name from branches.name.

Revision ID: 0044_shop_name_backfill
Revises: 0043_backup_import
Create Date: 2026-11-13
"""
from alembic import op

revision = "0044_shop_name_backfill"
down_revision = "0043_backup_import"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Backfill shop_identity.shop_name from earliest active branch name.

    Idempotent: safe on empty DBs (no branches -> no-op), fresh installs
    (already set -> no-op), and already-migrated DBs.
    """
    op.execute("""
        UPDATE shop_identity
        SET shop_name = (
            SELECT name FROM branches
            WHERE is_active = true AND name IS NOT NULL AND TRIM(name) <> ''
            ORDER BY created_at ASC
            LIMIT 1
        )
        WHERE (shop_name IS NULL OR TRIM(shop_name) = '')
          AND EXISTS (
              SELECT 1 FROM branches
              WHERE is_active = true AND name IS NOT NULL AND TRIM(name) <> ''
          );
    """)


def downgrade() -> None:
    """Data migration — not reversible."""
    pass
