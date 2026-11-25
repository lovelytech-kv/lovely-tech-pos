"""Item buy cost, admin review flag and low-stock threshold

Revision ID: 0046_item_cost_review_threshold
Revises: 0045_pitr_base_backups
Create Date: 2026-11-25
"""
from alembic import op

revision = "0046_item_cost_review_threshold"
down_revision = "0045_pitr_base_backups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS buy_cost NUMERIC(12,2)")
    op.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS needs_admin_review BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS low_stock_threshold INTEGER NOT NULL DEFAULT 5")
    op.execute("CREATE INDEX IF NOT EXISTS ix_items_needs_admin_review ON items(needs_admin_review) WHERE needs_admin_review = true")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_items_needs_admin_review")
    op.execute("ALTER TABLE items DROP COLUMN IF EXISTS low_stock_threshold")
    op.execute("ALTER TABLE items DROP COLUMN IF EXISTS needs_admin_review")
    op.execute("ALTER TABLE items DROP COLUMN IF EXISTS buy_cost")
