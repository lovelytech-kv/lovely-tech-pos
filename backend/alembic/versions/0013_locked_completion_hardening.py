"""Locked v2 completion hardening.

Adds configurable cashier discount limit, repair-payment proof reference,
and explicit damage-review status for repair/stock loss workflows.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013_locked_completion_hardening"
down_revision = "0012_return_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("discount_limit_percent", sa.Numeric(5, 2), nullable=False, server_default="0"))
    op.create_check_constraint("ck_users_discount_limit_percent", "users", "discount_limit_percent >= 0 AND discount_limit_percent <= 100")
    op.add_column("repair_payments", sa.Column("proof_reference", sa.String(150), nullable=True))
    op.add_column("damage_loss_records", sa.Column("review_status", sa.String(30), nullable=False, server_default="APPROVED"))
    op.create_index("ix_damage_loss_review_status", "damage_loss_records", ["branch_id", "review_status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_damage_loss_review_status", table_name="damage_loss_records")
    op.drop_column("damage_loss_records", "review_status")
    op.drop_column("repair_payments", "proof_reference")
    op.drop_constraint("ck_users_discount_limit_percent", "users", type_="check")
    op.drop_column("users", "discount_limit_percent")
