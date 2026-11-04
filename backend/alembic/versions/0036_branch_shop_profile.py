"""Branch shop profile fields

Revision ID: 0036_branch_shop_profile
Revises: 0035_import_mapping_persistence
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0036_branch_shop_profile"
down_revision = "0035_import_mapping_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('branches', sa.Column('address', sa.String(255), nullable=True))
    op.add_column('branches', sa.Column('phone', sa.String(50), nullable=True))
    op.add_column('branches', sa.Column('email', sa.String(120), nullable=True))
    op.add_column('branches', sa.Column('logo_base64', sa.Text(), nullable=True))
    op.add_column('branches', sa.Column('logo_mime', sa.String(50), nullable=True))
    op.add_column(
        'branches',
        sa.Column('invoice_prefix', sa.String(20), server_default='INV', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('branches', 'invoice_prefix')
    op.drop_column('branches', 'logo_mime')
    op.drop_column('branches', 'logo_base64')
    op.drop_column('branches', 'email')
    op.drop_column('branches', 'phone')
    op.drop_column('branches', 'address')