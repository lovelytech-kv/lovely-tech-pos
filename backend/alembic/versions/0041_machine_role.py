"""Machine role identity

Revision ID: 0041_machine_role
Revises: 0040_shop_identity
Create Date: 2026-11-08
"""
import uuid
from alembic import op
import sqlalchemy as sa

revision = "0041_machine_role"
down_revision = "0040_shop_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'machine_identity',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('machine_role', sa.String(10), nullable=False, server_default='SERVER'),
        sa.Column('machine_name', sa.String(100), nullable=True),
        sa.Column('server_url', sa.String(255), nullable=True),
        sa.Column('registered_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("machine_role IN ('SERVER', 'CLIENT')", name='ck_machine_role_valid'),
    )

    # Seed one row as SERVER (existing dev machine)
    seed_id = uuid.uuid4()
    op.execute(
        f"INSERT INTO machine_identity (id, machine_role, registered_at) "
        f"VALUES ('{seed_id}', 'SERVER', NOW())"
    )


def downgrade() -> None:
    op.drop_table('machine_identity')