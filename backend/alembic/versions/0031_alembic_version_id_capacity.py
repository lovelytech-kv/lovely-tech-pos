"""Ensure alembic_version.version_num can store revision IDs over 32 chars.

Revision ID: 0031_alembic_version_id_capacity
Revises: 0030_audit_immutability

Safety/final schema adjustment: widens alembic_version.version_num to
VARCHAR(64) when it is still narrower (Alembic's default is VARCHAR(32),
which cannot hold revision IDs such as
0028_sale_return_exchange_version_lock). Fresh databases already get the
wide column from alembic/env.py before the first revision runs, so this is
a no-op there; it protects databases whose version table was created by
older tooling. Existing data is preserved: widening a varchar never fails.
"""
import sqlalchemy as sa
from alembic import op

revision = "0031_alembic_version_id_capacity"
down_revision = "0030_audit_immutability"
branch_labels = None
depends_on = None

MIN_VERSION_NUM_LENGTH = 64


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("alembic_version"):
        return
    for column in inspector.get_columns("alembic_version"):
        if column["name"] != "version_num":
            continue
        length = getattr(column["type"], "length", None)
        if length is None or length >= MIN_VERSION_NUM_LENGTH:
            return
        op.execute(
            "ALTER TABLE alembic_version "
            "ALTER COLUMN version_num TYPE VARCHAR(64)"
        )
        return


def downgrade() -> None:
    # Intentionally a no-op: narrowing back to VARCHAR(32) would fail once
    # revision IDs longer than 32 characters have been recorded.
    return
