"""Add persistent authenticated sessions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='0007_auth_sessions'; down_revision='0006_integrity_indexes'; branch_labels=None; depends_on=None

def upgrade():
    op.create_table(
        'user_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(length=128), unique=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_user_sessions_user_active','user_sessions',['user_id','revoked_at','expires_at'])

def downgrade():
    op.drop_index('ix_user_sessions_user_active', table_name='user_sessions')
    op.drop_table('user_sessions')
