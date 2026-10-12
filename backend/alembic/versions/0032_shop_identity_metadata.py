"""Add versioned canonical shop identity metadata.

Revision ID: 0032_shop_identity_metadata
Revises: 0031_alembic_version_id_capacity
"""
from alembic import op
import sqlalchemy as sa

revision = "0032_shop_identity_metadata"
down_revision = "0031_alembic_version_id_capacity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_identity",
        sa.Column("identity_key", sa.String(length=16), nullable=False),
        sa.Column("shop_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("identity_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "identity_key = 'primary'",
            name="ck_shop_identity_singleton_key",
        ),
        sa.CheckConstraint(
            "identity_version = 1",
            name="ck_shop_identity_version",
        ),
        sa.PrimaryKeyConstraint("identity_key"),
        sa.UniqueConstraint("shop_id", name="uq_shop_identity_shop_id"),
    )

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("""
        CREATE FUNCTION ltpos_shop_identity_immutable() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE'
             OR OLD.identity_key IS DISTINCT FROM NEW.identity_key
             OR OLD.shop_id IS DISTINCT FROM NEW.shop_id THEN
            RAISE EXCEPTION 'Canonical shop identity cannot be changed or deleted';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)
        op.execute("""
        CREATE TRIGGER trg_shop_identity_immutable
        BEFORE UPDATE OR DELETE ON shop_identity
        FOR EACH ROW EXECUTE FUNCTION ltpos_shop_identity_immutable()
        """)
    elif dialect == "sqlite":
        op.execute("""
        CREATE TRIGGER trg_shop_identity_immutable_update
        BEFORE UPDATE ON shop_identity
        WHEN OLD.identity_key != NEW.identity_key OR OLD.shop_id != NEW.shop_id
        BEGIN
          SELECT RAISE(ABORT, 'Canonical shop identity cannot be changed');
        END
        """)
        op.execute("""
        CREATE TRIGGER trg_shop_identity_immutable_delete
        BEFORE DELETE ON shop_identity
        BEGIN
          SELECT RAISE(ABORT, 'Canonical shop identity cannot be deleted');
        END
        """)
    else:
        raise RuntimeError(f"Unsupported dialect for shop identity migration: {dialect}")


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_shop_identity_immutable ON shop_identity")
        op.execute("DROP FUNCTION IF EXISTS ltpos_shop_identity_immutable()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_shop_identity_immutable_update")
        op.execute("DROP TRIGGER IF EXISTS trg_shop_identity_immutable_delete")
    op.drop_table("shop_identity")
