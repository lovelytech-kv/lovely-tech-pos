"""Add payment_method to purchases.

Revision ID: 0027_purchase_payment_method
Revises: 0026_return_payment_timestamps
"""
from alembic import op
import sqlalchemy as sa


revision = "0027_purchase_payment_method"
down_revision = "0026_return_payment_timestamps"
branch_labels = None
depends_on = None


def upgrade():
    # Purchases previously carried no payment method. Historical purchases
    # defaulted to physical-cash outflows in every cash report, so the least
    # disruptive / backward-compatible default is CASH for existing rows and
    # for any new row that omits the value. Valid values (CASH/CARD/ONLINE)
    # are enforced by the application layer, matching the convention used by
    # the expenses, payments and settlement payment_method columns.
    op.add_column(
        "purchases",
        sa.Column("payment_method", sa.String(30), nullable=False, server_default="CASH"),
    )
    op.execute(
        sa.text(
            """
            UPDATE purchases
            SET payment_method = 'CASH'
            WHERE payment_method IS NULL
            """
        )
    )


def downgrade():
    op.drop_column("purchases", "payment_method")
