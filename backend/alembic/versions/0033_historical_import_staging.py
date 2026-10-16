"""historical import staging

Revision ID: 0033_historical_import_staging
Revises: 0032_shop_identity_metadata
Create Date: 2026-10-13 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0033_historical_import_staging'
down_revision = '0032_shop_identity_metadata'
branch_labels = None
depends_on = None

def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table('import_batches',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('branch_id', uuid, sa.ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('uploaded_by', uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('status', sa.String(length=50), nullable=False, server_default="PENDING_APPROVAL"),
        sa.Column('approved_by', uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('import_staging_rows',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('batch_id', uuid, sa.ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),
        sa.Column('row_type', sa.String(length=50), nullable=False),
        sa.Column('raw_data', sa.JSON(), nullable=False),
        sa.Column('validation_status', sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column('error_details', sa.Text(), nullable=True),
        sa.Column('reference_id', uuid, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('import_staging_rows')
    op.drop_table('import_batches')
