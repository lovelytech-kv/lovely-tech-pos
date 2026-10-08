"""Item master and purchase-entry permissions.
Revision ID: 0011_item_purchase_hardening
Revises: 0010_recovery_controls
"""
from alembic import op, context
import sqlalchemy as sa
import uuid
revision="0011_item_purchase_hardening"
down_revision="0010_recovery_controls"
branch_labels=None
depends_on=None

def upgrade():
    if context.is_offline_mode():
        return
    bind=op.get_bind()
    rows=bind.execute(sa.text("SELECT id, code FROM permissions WHERE code IN ('ITEM_EDIT','PURCHASE_ENTRY')")).mappings().all()
    existing={r['code']:r['id'] for r in rows}
    for code,name,desc in [
        ('ITEM_EDIT','Item Master Edit','Create and edit item master records and barcodes'),
        ('PURCHASE_ENTRY','Purchase Entry','Create purchase entries without supplier cost'),
    ]:
        if code not in existing:
            pid=uuid.uuid4(); bind.execute(sa.text("INSERT INTO permissions(id,code,name,description) VALUES (:id,:code,:name,:description)"),dict(id=pid,code=code,name=name,description=desc)); existing[code]=pid
    admin=bind.execute(sa.text("SELECT id FROM roles WHERE upper(code)='ADMIN'")).scalar()
    cashier=bind.execute(sa.text("SELECT id FROM roles WHERE upper(code)='CASHIER'")).scalar()
    for rid,code in [(admin,'ITEM_EDIT'),(admin,'PURCHASE_ENTRY'),(cashier,'ITEM_EDIT'),(cashier,'PURCHASE_ENTRY')]:
        if rid:
            pid=existing[code]
            bind.execute(sa.text("INSERT INTO role_permissions(role_id,permission_id) VALUES (:rid,:pid) ON CONFLICT DO NOTHING"),dict(rid=rid,pid=pid))

def downgrade():
    if context.is_offline_mode():
        return
    bind=op.get_bind(); bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN ('ITEM_EDIT','PURCHASE_ENTRY'))")); bind.execute(sa.text("DELETE FROM permissions WHERE code IN ('ITEM_EDIT','PURCHASE_ENTRY')"))
