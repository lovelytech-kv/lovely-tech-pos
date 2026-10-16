"""import batch idempotency columns

Revision ID: 0036_import_batch_idempotency
Revises: 0035_import_mapping_persistence
Create Date: 2026-10-13 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = '0036_import_batch_idempotency'
down_revision = '0035_import_mapping_persistence'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add columns as nullable to avoid default conflicts
    op.add_column(
        "import_batches",
        sa.Column("import_type", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "import_batches",
        sa.Column("content_hash", sa.String(length=64), nullable=True)
    )

    # Step 2: Populate import_type from existing staging rows
    # For each batch, look up the row_type from its first staging row
    op.execute(text("""
        UPDATE import_batches
        SET import_type = (
            SELECT row_type
            FROM import_staging_rows
            WHERE import_staging_rows.batch_id = import_batches.id
            LIMIT 1
        )
        WHERE import_type IS NULL
    """))

    # Step 3: For any remaining NULL import_type, default to 'ITEM'
    op.execute(text("""
        UPDATE import_batches
        SET import_type = 'ITEM'
        WHERE import_type IS NULL
    """))

    # Step 4: Populate content_hash for existing rows using a deterministic unique value
    # Use SHA256 of (batch_id || filename || uploaded_at) to ensure uniqueness
    op.execute(text("""
        UPDATE import_batches
        SET content_hash = encode(digest(id::text || filename || uploaded_at::text, 'sha256'), 'hex')
        WHERE content_hash IS NULL
    """))

    # Step 5: Make columns NOT NULL now that all rows have values
    op.alter_column("import_batches", "import_type", nullable=False)
    op.alter_column("import_batches", "content_hash", nullable=False)

    # Step 6: Create unique constraint for idempotency
    op.create_unique_constraint(
        "uq_import_batch_dedupe",
        "import_batches",
        ["branch_id", "uploaded_by", "import_type", "content_hash"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_import_batch_dedupe", "import_batches", type_="unique")
    op.drop_column("import_batches", "content_hash")
    op.drop_column("import_batches", "import_type")