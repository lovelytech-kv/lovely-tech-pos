"""Machine identity — join audit fields (Chunk 13)

Revision ID: 0042_machine_join_audit
Revises: 0041_machine_role
Create Date: 2026-11-09
"""
from alembic import op

revision = "0042_machine_join_audit"
down_revision = "0041_machine_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent — safe to re-run if partial failure occurred previously
    op.execute(
        "ALTER TABLE machine_identity "
        "ADD COLUMN IF NOT EXISTS server_shop_uuid VARCHAR(36) NULL"
    )
    op.execute(
        "ALTER TABLE machine_identity "
        "ADD COLUMN IF NOT EXISTS last_join_at TIMESTAMPTZ NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE machine_identity DROP COLUMN IF EXISTS last_join_at")
    op.execute("ALTER TABLE machine_identity DROP COLUMN IF EXISTS server_shop_uuid")