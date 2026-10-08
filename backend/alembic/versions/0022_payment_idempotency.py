"""Add idempotency keys to financial payment events."""
from alembic import op
import sqlalchemy as sa

revision = "0022_payment_idempotency"
down_revision = "0021_target_progress_snapshots"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("repair_payments", sa.Column("idempotency_key", sa.String(length=200), nullable=True))
    op.add_column("return_payments", sa.Column("idempotency_key", sa.String(length=200), nullable=True))
    op.add_column("credit_settlements", sa.Column("idempotency_key", sa.String(length=200), nullable=True))
    op.create_unique_constraint("uq_repair_payments_idempotency_key", "repair_payments", ["idempotency_key"])
    op.create_unique_constraint("uq_return_payments_idempotency_key", "return_payments", ["idempotency_key"])
    op.create_unique_constraint("uq_credit_settlements_idempotency_key", "credit_settlements", ["idempotency_key"])

def downgrade() -> None:
    op.drop_constraint("uq_credit_settlements_idempotency_key", "credit_settlements", type_="unique")
    op.drop_constraint("uq_return_payments_idempotency_key", "return_payments", type_="unique")
    op.drop_constraint("uq_repair_payments_idempotency_key", "repair_payments", type_="unique")
    op.drop_column("credit_settlements", "idempotency_key")
    op.drop_column("return_payments", "idempotency_key")
    op.drop_column("repair_payments", "idempotency_key")
