"""Seed IMPORT_MANAGE permission

Revision ID: 0034_seed_import_manage_permission
Revises: 0033_historical_import_staging
Create Date: 2026-10-13 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0034_seed_import_manage_permission'
down_revision = '0033_historical_import_staging'
branch_labels = None
depends_on = None

def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    # Insert IMPORT_MANAGE permission if not exists
    op.execute("""
        INSERT INTO permissions (id, code, name, description, created_at, updated_at)
        VALUES (gen_random_uuid(), 'IMPORT_MANAGE', 'Manage Imports', 'Permission to upload and preview historical import batches', NOW(), NOW())
        ON CONFLICT (code) DO NOTHING
    """)
    # Assign to ADMIN role (ADMIN bypasses permission check, but this makes it explicit)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r, permissions p
        WHERE r.code = 'ADMIN' AND p.code = 'IMPORT_MANAGE'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)

def downgrade() -> None:
    # Remove role_permissions for IMPORT_MANAGE
    op.execute("""
        DELETE FROM role_permissions
        WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'IMPORT_MANAGE')
    """)
    # Remove IMPORT_MANAGE permission
    op.execute("""
        DELETE FROM permissions WHERE code = 'IMPORT_MANAGE'
    """)