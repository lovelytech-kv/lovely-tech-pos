"""recovery controls and stock indexes"""
from alembic import op
import sqlalchemy as sa
revision='0010_recovery_controls'; down_revision='0009'; branch_labels=None; depends_on=None

def upgrade():
    op.create_table('admin_recovery_codes',
        sa.Column('id',sa.Uuid(),primary_key=True,nullable=False),
        sa.Column('code_hash',sa.String(128),nullable=False,unique=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('created_by',sa.Uuid(),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('used_at',sa.DateTime(timezone=True)),
        sa.Column('used_by',sa.Uuid(),sa.ForeignKey('users.id',ondelete='RESTRICT')),
    )
    op.create_index('ix_stock_movements_item_time','stock_movements',['branch_id','item_id','occurred_at'])

def downgrade():
    op.drop_index('ix_stock_movements_item_time',table_name='stock_movements')
    op.drop_table('admin_recovery_codes')
