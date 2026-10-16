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


def _check_empty_batches(conn) -> list:
    """Return list of batch IDs that have no staging rows."""
    result = conn.execute(text("""
        SELECT ib.id
        FROM import_batches ib
        LEFT JOIN import_staging_rows isr ON isr.batch_id = ib.id
        WHERE isr.id IS NULL
    """))
    return [row[0] for row in result.fetchall()]


def _check_mixed_type_batches(conn) -> list:
    """Return list of batch IDs that have mixed row_type values in staging rows."""
    result = conn.execute(text("""
        SELECT batch_id, COUNT(DISTINCT row_type) as type_count
        FROM import_staging_rows
        GROUP BY batch_id
        HAVING COUNT(DISTINCT row_type) > 1
    """))
    return [row[0] for row in result.fetchall()]


def _get_batch_details(conn, batch_ids: list) -> list:
    """Return detailed info for given batch IDs for error reporting."""
    if not batch_ids:
        return []
    placeholders = ", ".join([f"'{bid}'" for bid in batch_ids])
    result = conn.execute(text(f"""
        SELECT ib.id, ib.filename, ib.uploaded_at,
               COUNT(isr.id) as row_count,
               STRING_AGG(DISTINCT isr.row_type, ', ') as row_types
        FROM import_batches ib
        LEFT JOIN import_staging_rows isr ON isr.batch_id = ib.id
        WHERE ib.id IN ({placeholders})
        GROUP BY ib.id, ib.filename, ib.uploaded_at
    """))
    return [
        {
            "id": str(row[0]),
            "filename": row[1],
            "uploaded_at": str(row[2]),
            "row_count": row[3],
            "row_types": row[4] or "none",
        }
        for row in result.fetchall()
    ]


def upgrade() -> None:
    conn = op.get_bind()

    # Step 0: Validate legacy data before making changes
    # Requirements: "Never fabricate missing historical records; unresolved data must be reported for human disposition."
    # Requirements: "Migrations must preserve existing business data and fail explicitly when unsafe duplicates or invalid states exist."

    empty_batches = _check_empty_batches(conn)
    if empty_batches:
        details = _get_batch_details(conn, empty_batches)
        detail_str = "; ".join(
            f"batch {d['id']} (file: {d['filename']}, uploaded: {d['uploaded_at']}, rows: {d['row_count']})"
            for d in details
        )
        raise RuntimeError(
            f"Migration 0036 blocked: {len(empty_batches)} import batch(es) have no staging rows. "
            f"Cannot determine import_type for empty batches. "
            f"Per requirements, missing historical records must not be fabricated. "
            f"Affected batches: {detail_str}. "
            f"Resolve by deleting empty batches or adding staging rows before re-running migration."
        )

    mixed_type_batches = _check_mixed_type_batches(conn)
    if mixed_type_batches:
        details = _get_batch_details(conn, mixed_type_batches)
        detail_str = "; ".join(
            f"batch {d['id']} (file: {d['filename']}, types: {d['row_types']})"
            for d in details
        )
        raise RuntimeError(
            f"Migration 0036 blocked: {len(mixed_type_batches)} import batch(es) have mixed row_type values in staging rows. "
            f"Cannot arbitrarily choose a single import_type. "
            f"Per requirements, invalid states must fail explicitly. "
            f"Affected batches: {detail_str}. "
            f"Resolve by splitting batches or correcting row_type values before re-running migration."
        )

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
    # Each batch now guaranteed to have exactly one distinct row_type
    op.execute(text("""
        UPDATE import_batches
        SET import_type = (
            SELECT DISTINCT row_type
            FROM import_staging_rows
            WHERE import_staging_rows.batch_id = import_batches.id
        )
        WHERE import_type IS NULL
    """))

    # Step 3: Populate content_hash for existing rows using a deterministic unique value
    # Use SHA256 of (batch_id || filename || uploaded_at) to ensure uniqueness.
    # sha256(bytea) and encode(bytea, 'hex') are built-in PostgreSQL functions;
    # digest() would require the pgcrypto extension, which is not declared.
    op.execute(text("""
        UPDATE import_batches
        SET content_hash = encode(sha256((id::text || filename || uploaded_at::text)::bytea), 'hex')
        WHERE content_hash IS NULL
    """))

    # Step 4: Verify all batches now have import_type (safety check)
    remaining_null = conn.execute(text("""
        SELECT COUNT(*) FROM import_batches WHERE import_type IS NULL
    """)).scalar()
    if remaining_null > 0:
        raise RuntimeError(
            f"Migration 0036 internal error: {remaining_null} batch(es) still have NULL import_type after population. "
            f"This should not happen after validation checks."
        )

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


