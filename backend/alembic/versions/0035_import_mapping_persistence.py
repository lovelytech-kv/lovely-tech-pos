"""Bridge migration for 0035_import_mapping_persistence.

The original 0035 migration file was never committed to the repository.
The schema changes it contained were applied to the live dev DB manually
(via SQL). This bridge file aligns alembic history so fresh installs work.

No-op for existing DBs.

Revision ID: 0035_import_mapping_persistence
Revises: 0034_damage_loss_type
Create Date: 2026-11-03
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0035_import_mapping_persistence"
down_revision = "0034_damage_loss_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op — the original 0035 changes were applied manually.

    Tables/columns already exist in the live DB. This bridge only aligns
    the alembic history so fresh installs (`alembic upgrade head`) succeed.
    """
    pass


def downgrade() -> None:
    """No-op — nothing to reverse."""
    pass