"""Items can list the other phone/laptop models they are compatible with (Requirements 04).

Revision ID: 0033_item_compatible_models
Revises: 0032_purchase_no_payment_method
"""
from alembic import op
import sqlalchemy as sa

revision = "0033_item_compatible_models"
down_revision = "0032_purchase_no_payment_method"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("items", sa.Column("compatible_models", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("items", "compatible_models")
