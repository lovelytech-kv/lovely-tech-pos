"""operations admin backup foundations

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0009'
down_revision = '0008_sales_cost_and_integrity'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('day_sessions', sa.Column('opening_denominations', postgresql.JSONB(), nullable=True))
    op.add_column('day_ends', sa.Column('actual_denominations', postgresql.JSONB(), nullable=True))
    op.create_table(
        'backup_points',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('branch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('branches.id', ondelete='RESTRICT')),
        sa.Column('state', sa.String(30), nullable=False),
        sa.Column('storage_target', sa.String(300), nullable=False),
        sa.Column('filename', sa.String(300), nullable=False),
        sa.Column('sha256', sa.String(128)),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT')),
        sa.Column('verified_at', sa.DateTime(timezone=True)),
        sa.Column('failure_reason', sa.Text()),
    )
    op.create_index('ix_backup_points_state', 'backup_points', ['state','verified_at'])
    op.create_table(
        'restore_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('branch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('branches.id', ondelete='RESTRICT')),
        sa.Column('backup_point_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('backup_points.id', ondelete='RESTRICT')),
        sa.Column('actor_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT')),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('reason', sa.Text()),
    )

def downgrade():
    op.drop_table('restore_events')
    op.drop_index('ix_backup_points_state', table_name='backup_points')
    op.drop_table('backup_points')
    op.drop_column('day_ends','actual_denominations')
    op.drop_column('day_sessions','opening_denominations')
