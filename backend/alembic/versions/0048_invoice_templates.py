"""Invoice / receipt templates (80mm + A4)

Revision ID: 0048_invoice_templates
Revises: 0047_fk_indexes
Create Date: 2026-11-26

Session 3C-2. Templates drive receipt layout at print time. The
"Software by Lovely Tech" footer is NOT part of this table: it is appended
by the receipt builder and is never user-editable.
"""
from alembic import op

revision = '0048_invoice_templates'
down_revision = '0047_fk_indexes'
branch_labels = None
depends_on = None

# Stable seed ids keep the migration idempotent and make defaults easy to find.
SEED_80MM_ID = 'd3c4a1b0-0001-4000-8000-000000000001'
SEED_A4_ID = 'd3c4a1b0-0002-4000-8000-000000000002'


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS invoice_templates (
            id UUID PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            paper_size VARCHAR(10) NOT NULL,
            is_default BOOLEAN NOT NULL DEFAULT false,
            is_active BOOLEAN NOT NULL DEFAULT true,
            show_logo BOOLEAN NOT NULL DEFAULT true,
            header_text TEXT,
            show_address BOOLEAN NOT NULL DEFAULT true,
            show_phone BOOLEAN NOT NULL DEFAULT true,
            show_email BOOLEAN NOT NULL DEFAULT false,
            show_customer_name BOOLEAN NOT NULL DEFAULT true,
            show_customer_phone BOOLEAN NOT NULL DEFAULT true,
            show_item_description BOOLEAN NOT NULL DEFAULT true,
            show_item_code BOOLEAN NOT NULL DEFAULT true,
            show_unit_price BOOLEAN NOT NULL DEFAULT true,
            show_warranty_info BOOLEAN NOT NULL DEFAULT true,
            show_repair_details BOOLEAN NOT NULL DEFAULT true,
            footer_text TEXT,
            warranty_terms TEXT,
            show_footer_note BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_by UUID REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    # Constraint is added separately so a partially-created table still converges.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoice_templates_paper_size'
            ) THEN
                ALTER TABLE invoice_templates
                    ADD CONSTRAINT ck_invoice_templates_paper_size
                    CHECK (paper_size IN ('80mm', 'A4'));
            END IF;
        END
        $$
    """)

    # At most one active default per paper size.
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_invoice_templates_default_paper
            ON invoice_templates (paper_size)
            WHERE is_default AND is_active
    """)

    # Seed defaults only when that paper size has no default yet.
    op.execute(f"""
        INSERT INTO invoice_templates
            (id, name, paper_size, is_default, is_active, show_logo, header_text,
             show_address, show_phone, show_email, show_customer_name,
             show_customer_phone, show_item_description, show_item_code,
             show_unit_price, show_warranty_info, show_repair_details,
             footer_text, warranty_terms, show_footer_note, created_at, updated_at,
             created_by)
        SELECT
            '{SEED_80MM_ID}', 'Default 80mm', '80mm', true, true, true, NULL,
            true, true, false, true,
            true, true, true,
            true, true, true,
            'Thank you for shopping at {{shop_name}}!', NULL, true, NOW(), NOW(),
            NULL
        WHERE NOT EXISTS (
            SELECT 1 FROM invoice_templates WHERE paper_size = '80mm' AND is_default
        )
    """)
    op.execute(f"""
        INSERT INTO invoice_templates
            (id, name, paper_size, is_default, is_active, show_logo, header_text,
             show_address, show_phone, show_email, show_customer_name,
             show_customer_phone, show_item_description, show_item_code,
             show_unit_price, show_warranty_info, show_repair_details,
             footer_text, warranty_terms, show_footer_note, created_at, updated_at,
             created_by)
        SELECT
            '{SEED_A4_ID}', 'Default A4', 'A4', true, true, true, NULL,
            true, true, true, true,
            true, true, true,
            true, true, true,
            'Thank you for shopping at {{shop_name}}!', NULL, true, NOW(), NOW(),
            NULL
        WHERE NOT EXISTS (
            SELECT 1 FROM invoice_templates WHERE paper_size = 'A4' AND is_default
        )
    """)


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS ux_invoice_templates_default_paper')
    op.execute('DROP TABLE IF EXISTS invoice_templates')
