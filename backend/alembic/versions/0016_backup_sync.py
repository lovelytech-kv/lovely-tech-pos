"""Add optional verified-backup Google Drive sync state."""
from alembic import op
import sqlalchemy as sa
revision='0016_backup_sync'; down_revision='0015_manual_warranty_reference'; branch_labels=None; depends_on=None

def upgrade():
    op.add_column('backup_points',sa.Column('sync_state',sa.String(30),nullable=False,server_default='LOCAL_ONLY'))
    op.add_column('backup_points',sa.Column('remote_path',sa.String(500),nullable=True))
    op.create_index('ix_backup_points_sync_state','backup_points',['branch_id','sync_state','verified_at'])

def downgrade():
    op.drop_index('ix_backup_points_sync_state',table_name='backup_points')
    op.drop_column('backup_points','remote_path'); op.drop_column('backup_points','sync_state')
