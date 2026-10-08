"""Sale/Return/Exchange optimistic-locking foundation.

Revision ID: 0028_sale_return_exchange_version_lock
Revises: 0027_purchase_payment_method
"""
from alembic import op
import sqlalchemy as sa


revision = "0028_sale_return_exchange_version_lock"
down_revision = "0027_purchase_payment_method"
branch_labels = None
depends_on = None


def upgrade():
    # Sale, Return and Exchange already carry an integer `version` column
    # (created in 0003_sales_warranty with server_default="1"). This migration
    # advances the chain to mark the point where the application layer began
    # enforcing optimistic locking on those three entities. No schema change is
    # required; existing rows keep their current version values.
    pass


def downgrade():
    pass