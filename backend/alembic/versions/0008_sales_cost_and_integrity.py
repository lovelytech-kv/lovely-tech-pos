"""Persist sale FIFO cost and tighten payment source integrity."""
from alembic import op
import sqlalchemy as sa

revision = "0008_sales_cost_and_integrity"
down_revision = "0007_auth_sessions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sales", sa.Column("total_cost", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.alter_column("sales", "total_cost", server_default=None)
    op.create_check_constraint("ck_payments_one_source", "payments", "((sale_id IS NOT NULL)::int + (settlement_id IS NOT NULL)::int) = 1")
    op.create_index("ix_payments_settlement", "payments", ["settlement_id"])


def downgrade():
    op.drop_index("ix_payments_settlement", table_name="payments")
    op.drop_constraint("ck_payments_one_source", "payments", type_="check")
    op.drop_column("sales", "total_cost")
