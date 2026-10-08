"""Integrity constraints and reporting indexes."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='0006_integrity_indexes'; down_revision='0005_finance_day_approval'; branch_labels=None; depends_on=None

def upgrade():
    # One active business day per branch/date; historical closed days remain allowed.
    op.create_index('ix_day_sessions_open_unique','day_sessions',['branch_id','business_date'],unique=True,postgresql_where=sa.text("status IN ('OPEN','SHIFT_ENDED')"))
    op.create_index('ix_sales_branch_datetime_status','sales',['branch_id','sale_datetime','status'])
    op.create_index('ix_payments_sale_method','payments',['sale_id','payment_method'])
    op.create_index('ix_expenses_branch_date_status','expenses',['branch_id','expense_date','status'])
    op.create_index('ix_other_income_branch_date_status','other_income',['branch_id','income_date','status'])
    op.create_index('ix_repairs_branch_date','repairs',['branch_id','date_in'])

def downgrade():
    for name,table in [('ix_repairs_branch_date','repairs'),('ix_other_income_branch_date_status','other_income'),('ix_expenses_branch_date_status','expenses'),('ix_payments_sale_method','payments'),('ix_sales_branch_datetime_status','sales'),('ix_day_sessions_open_unique','day_sessions')]:
        op.drop_index(name,table_name=table)
