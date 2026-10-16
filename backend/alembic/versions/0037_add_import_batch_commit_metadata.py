"""add commit metadata to import_batches

Revision ID: 0037
Revises: 0036_import_batch_idempotency
Create Date: 20261015-161538

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0037'
down_revision = '0036_import_batch_idempotency'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "import_batches",
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "import_batches",
        sa.Column("committed_by", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_import_batches_committed_by_users",
        "import_batches",
        "users",
        ["committed_by"],
        ["id"],
        ondelete="RESTRICT"
    )
    op.add_column(
        "import_batches",
        sa.Column("commit_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        "import_batches",
        sa.Column("failure_reason", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_constraint("fk_import_batches_committed_by_users", "import_batches", type_="foreignkey")
    op.drop_column("import_batches", "failure_reason")
    op.drop_column("import_batches", "commit_result")
    op.drop_column("import_batches", "committed_by")
    op.drop_column("import_batches", "committed_at")
