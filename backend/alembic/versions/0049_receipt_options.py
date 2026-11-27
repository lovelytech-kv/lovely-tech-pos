"""Invoice template receipt options (B&W logo, extra fields, A5/A6)

Revision ID: 0049_receipt_options
Revises: 0048_invoice_templates
Create Date: 2026-11-27

Session 3D-1. Adds receipt toggles used by the print builder and widens the
paper-size constraint to include A5 and A6. Existing templates keep their
current output: every new boolean defaults to false.
"""
from alembic import op

revision = '0049_receipt_options'
down_revision = '0048_invoice_templates'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD COLUMN IF NOT EXISTS keeps a partially-applied migration convergent.
    op.execute(
        'ALTER TABLE invoice_templates '
        'ADD COLUMN IF NOT EXISTS logo_monochrome BOOLEAN NOT NULL DEFAULT false'
    )
    op.execute(
        'ALTER TABLE invoice_templates '
        'ADD COLUMN IF NOT EXISTS show_payment_method BOOLEAN NOT NULL DEFAULT false'
    )
    op.execute(
        'ALTER TABLE invoice_templates '
        'ADD COLUMN IF NOT EXISTS show_cashier BOOLEAN NOT NULL DEFAULT false'
    )
    op.execute(
        'ALTER TABLE invoice_templates '
        'ADD COLUMN IF NOT EXISTS show_customer_notes BOOLEAN NOT NULL DEFAULT false'
    )

    # Recreate the paper-size check with A5/A6. Drop-then-add is idempotent.
    op.execute(
        'ALTER TABLE invoice_templates '
        'DROP CONSTRAINT IF EXISTS ck_invoice_templates_paper_size'
    )
    op.execute(
        'ALTER TABLE invoice_templates '
        "ADD CONSTRAINT ck_invoice_templates_paper_size "
        "CHECK (paper_size IN ('80mm', 'A4', 'A5', 'A6'))"
    )


def downgrade() -> None:
    # A5/A6 rows would violate the old constraint; remove them explicitly so a
    # downgrade cannot fail halfway. Templates for 80mm/A4 are preserved.
    op.execute("DELETE FROM invoice_templates WHERE paper_size IN ('A5', 'A6')")
    op.execute(
        'ALTER TABLE invoice_templates '
        'DROP CONSTRAINT IF EXISTS ck_invoice_templates_paper_size'
    )
    op.execute(
        'ALTER TABLE invoice_templates '
        "ADD CONSTRAINT ck_invoice_templates_paper_size "
        "CHECK (paper_size IN ('80mm', 'A4'))"
    )
    op.execute('ALTER TABLE invoice_templates DROP COLUMN IF EXISTS show_customer_notes')
    op.execute('ALTER TABLE invoice_templates DROP COLUMN IF EXISTS show_cashier')
    op.execute('ALTER TABLE invoice_templates DROP COLUMN IF EXISTS show_payment_method')
    op.execute('ALTER TABLE invoice_templates DROP COLUMN IF EXISTS logo_monochrome')
