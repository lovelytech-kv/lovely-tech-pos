"""Password recovery enhancements

Revision ID: 0039_password_recovery
Revises: 0038_system_settings
Create Date: 2026-11-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0039_password_recovery"
down_revision = "0038_system_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add revoked_at to admin_recovery_codes
    op.add_column(
        'admin_recovery_codes',
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'ix_admin_recovery_codes_active',
        'admin_recovery_codes',
        ['created_by', 'used_at', 'revoked_at'],
    )

    # Create password_reset_tokens for the new forgot-password flow
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            'user_id', sa.Uuid(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False,
        ),
        sa.Column('token_hash', sa.String(128), unique=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'ix_password_reset_tokens_user',
        'password_reset_tokens',
        ['user_id', 'used_at', 'expires_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_password_reset_tokens_user', 'password_reset_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_index('ix_admin_recovery_codes_active', 'admin_recovery_codes')
    op.drop_column('admin_recovery_codes', 'revoked_at')