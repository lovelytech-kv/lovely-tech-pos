"""Damage/loss records carry a type: DAMAGE, LOSS or INTERNAL_USE (Requirements 05).

Revision ID: 0034_damage_loss_type
Revises: 0033_item_compatible_models
"""
from alembic import op
import sqlalchemy as sa

revision = "0034_damage_loss_type"
down_revision = "0033_item_compatible_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("damage_loss_records", sa.Column("loss_type", sa.String(30), nullable=False, server_default="DAMAGE"))


def downgrade() -> None:
    op.drop_column("damage_loss_records", "loss_type")
