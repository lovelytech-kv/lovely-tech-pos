"""Placeholder — ImportMapping feature never shipped.

The ImportMapping persistence tables were planned for this revision but the
feature was never implemented or released. The original migration file was
never committed; this no-op placeholder is retained only to preserve the
alembic chain (0034 -> 0035 -> 0036, referenced by revision string in 0036).

No schema changes. Do not delete: existing databases may be stamped at
revision 0035_import_mapping_persistence.

ImportMapping is deferred to post-v1.0.

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
    """No-op — ImportMapping never shipped."""
    pass


def downgrade() -> None:
    """No-op — nothing to reverse."""
    pass
