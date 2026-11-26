"""Foreign-key lookup indexes + audit log action/time index

Revision ID: 0047_fk_indexes
Revises: 0046_item_cost_review_threshold
Create Date: 2026-11-26

M4/M21: child tables were missing indexes on their parent FK columns, forcing
sequential scans for every detail/history lookup.
M17: recovery-code rate limiting scans audit_log by action_type + timestamp.
"""
from alembic import op

revision = '0047_fk_indexes'
down_revision = '0046_item_cost_review_threshold'
branch_labels = None
depends_on = None

INDEXES = (
    ('ix_sale_lines_sale_id', 'sale_lines', 'sale_id'),
    ('ix_purchase_lines_purchase_id', 'purchase_lines', 'purchase_id'),
    ('ix_return_lines_return_id', 'return_lines', 'return_id'),
    ('ix_repair_parts_repair_id', 'repair_parts', 'repair_id'),
    ('ix_payments_settlement_id', 'payments', 'settlement_id'),
    ('ix_audit_log_action_time', 'audit_log', 'action_type, timestamp DESC'),
)


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.execute(f'CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})')


def downgrade() -> None:
    for name, _table, _columns in INDEXES:
        op.execute(f'DROP INDEX IF EXISTS {name}')
