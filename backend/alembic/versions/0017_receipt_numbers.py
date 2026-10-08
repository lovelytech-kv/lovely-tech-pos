"""Human-facing optional receipt numbers for repair/credit settlements."""
from alembic import op
import sqlalchemy as sa
revision='0017_receipt_numbers'; down_revision='0016_backup_sync'; branch_labels=None; depends_on=None

def upgrade():
    op.add_column('repair_payments',sa.Column('proof_no',sa.String(40),nullable=True))
    op.add_column('credit_settlements',sa.Column('proof_no',sa.String(40),nullable=True))
    op.create_unique_constraint('uq_repair_payment_proof_no','repair_payments',['proof_no'])
    op.create_unique_constraint('uq_credit_settlement_proof_no','credit_settlements',['proof_no'])

def downgrade():
    op.drop_constraint('uq_credit_settlement_proof_no','credit_settlements',type_='unique')
    op.drop_constraint('uq_repair_payment_proof_no','repair_payments',type_='unique')
    op.drop_column('credit_settlements','proof_no'); op.drop_column('repair_payments','proof_no')
