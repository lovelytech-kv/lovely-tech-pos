"""Reconcile manual warranty reference uniqueness with the existing 0015 constraint."""

# This migration originally attempted to create the same unique constraint that
# 0015_manual_warranty_reference already creates. Keeping the revision in the
# linear migration chain is useful for databases that already recorded it, but
# it must not create or drop the constraint a second time.

revision = "0019_manual_warranty_unique"
down_revision = "0018_permission_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Uniqueness is already enforced by 0015_manual_warranty_reference.
    # Intentionally no-op so fresh databases can progress past this revision.
    pass


def downgrade() -> None:
    # Do not remove the constraint owned by 0015 during a 0019 downgrade.
    pass
