"""Add version column to credit_settlements for optimistic locking.

Revision ID: 0029_credit_settlement_version
Revises: 0028_sale_return_exchange_version_lock
"""
from alembic import op
import sqlalchemy as sa


revision = "0029_credit_settlement_version"
down_revision = "0028_sale_return_exchange_version_lock"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "credit_settlements",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )


def downgrade():
    op.drop_column("credit_settlements", "version")