"""Purchases no longer record a payment method (Requirements 08).

Revision ID: 0032_purchase_no_payment_method
Revises: 0031_alembic_version_id_capacity
"""
from alembic import op

revision = "0032_purchase_no_payment_method"
down_revision = "0031_alembic_version_id_capacity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("purchases", "payment_method", nullable=True)
    op.execute("UPDATE purchases SET payment_method = NULL")


def downgrade() -> None:
    op.execute("UPDATE purchases SET payment_method = 'CASH' WHERE payment_method IS NULL")
    op.alter_column("purchases", "payment_method", nullable=False)
