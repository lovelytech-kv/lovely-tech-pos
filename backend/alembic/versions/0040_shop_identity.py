"""Shop identity table

Revision ID: 0040_shop_identity
Revises: 0039_password_recovery
Create Date: 2026-11-08
"""
import uuid
from alembic import op
import sqlalchemy as sa

revision = "0040_shop_identity"
down_revision = "0039_password_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'shop_identity',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('shop_uuid', sa.Uuid(as_uuid=True), unique=True, nullable=False),
        sa.Column('shop_name', sa.String(150), nullable=True),
        sa.Column('schema_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('upgraded_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Seed one row with a fresh shop_uuid (NEVER regenerated after this)
    seed_id = uuid.uuid4()
    seed_uuid = uuid.uuid4()
    op.execute(
        f"INSERT INTO shop_identity (id, shop_uuid, shop_name, schema_version, created_at) "
        f"VALUES ('{seed_id}', '{seed_uuid}', NULL, 1, NOW())"
    )


def downgrade() -> None:
    op.drop_table('shop_identity')