"""System settings table for admin-configurable session timeouts

Revision ID: 0038_system_settings
Revises: 0037_branch_dual_logo
Create Date: 2026-11-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0038_system_settings"
down_revision = "0037_branch_dual_logo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'system_settings',
        sa.Column('key', sa.String(80), primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.Uuid(as_uuid=True), nullable=True),
    )
    op.execute("""
        INSERT INTO system_settings (key, value, updated_at) VALUES
        ('session_timeout_admin_minutes', '5', NOW()),
        ('session_timeout_cashier_minutes', '60', NOW()),
        ('session_absolute_timeout_admin_hours', '12', NOW()),
        ('session_absolute_timeout_cashier_hours', '12', NOW())
    """)


def downgrade() -> None:
    op.drop_table('system_settings')