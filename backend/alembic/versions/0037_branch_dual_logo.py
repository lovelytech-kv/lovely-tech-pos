"""Branch dual light/dark logos

Revision ID: 0037_branch_dual_logo
Revises: 0036_branch_shop_profile
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0037_branch_dual_logo"
down_revision = "0036_branch_shop_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('branches', sa.Column('logo_base64_light', sa.Text(), nullable=True))
    op.add_column('branches', sa.Column('logo_mime_light', sa.String(50), nullable=True))
    op.add_column('branches', sa.Column('logo_base64_dark', sa.Text(), nullable=True))
    op.add_column('branches', sa.Column('logo_mime_dark', sa.String(50), nullable=True))
    # Migrate any existing logo to the LIGHT variant (existing logos were on light theme)
    op.execute("""
        UPDATE branches
        SET logo_base64_light = logo_base64,
            logo_mime_light = logo_mime
        WHERE logo_base64 IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_column('branches', 'logo_mime_dark')
    op.drop_column('branches', 'logo_base64_dark')
    op.drop_column('branches', 'logo_mime_light')
    op.drop_column('branches', 'logo_base64_light')