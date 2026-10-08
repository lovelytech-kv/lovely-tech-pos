"""Return refund payment ledger.
Revision ID: 0012_return_payments
Revises: 0011_item_purchase_hardening
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_return_payments"
down_revision = "0011_item_purchase_hardening"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "return_payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("return_id", sa.Uuid(), sa.ForeignKey("returns.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payment_method", sa.String(30), nullable=False),
        sa.Column("amount", sa.Numeric(18,2), nullable=False),
        sa.Column("payment_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference", sa.String(150)),
    )
    op.create_index("ix_return_payments_return", "return_payments", ["return_id"])
    op.create_index("ix_return_payments_datetime", "return_payments", ["payment_datetime"])

def downgrade():
    op.drop_index("ix_return_payments_datetime", table_name="return_payments")
    op.drop_index("ix_return_payments_return", table_name="return_payments")
    op.drop_table("return_payments")
