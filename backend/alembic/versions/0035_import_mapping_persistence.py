"""import mapping persistence

Revision ID: 0035_import_mapping_persistence
Revises: 0034_seed_import_manage_permission
Create Date: 2026-10-13 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0035_import_mapping_persistence'
down_revision = '0034_seed_import_manage_permission'
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table('import_mappings',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('batch_id', uuid, sa.ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column('import_type', sa.String(length=50), nullable=False),
        sa.Column('source_column', sa.String(length=255), nullable=False),
        sa.Column('target_field', sa.String(length=255), nullable=False),
        sa.Column('is_required', sa.String(length=10), nullable=False, server_default="false"),
        sa.Column('transform_hint', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('batch_id', 'source_column', name='uq_import_mapping_batch_source'),
        sa.UniqueConstraint('batch_id', 'target_field', name='uq_import_mapping_batch_target'),
    )


def downgrade() -> None:
    op.drop_table('import_mappings')