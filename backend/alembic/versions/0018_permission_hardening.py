"""Ensure locked cashier permission boundaries."""
from alembic import op
import sqlalchemy as sa
revision='0018_permission_hardening'; down_revision='0017_receipt_numbers'; branch_labels=None; depends_on=None

def upgrade():
    op.execute("""
    DELETE FROM role_permissions
    WHERE role_id IN (SELECT id FROM roles WHERE upper(code)='CASHIER')
      AND permission_id IN (SELECT id FROM permissions WHERE code IN ('CREDIT_SETTLE','CASH_HANDS_VIEW'))
    """)

def downgrade():
    pass
