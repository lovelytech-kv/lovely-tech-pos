"""Returns, exchanges and repair transaction foundation.

Revision ID: 0004_returns_exchange_repairs
Revises: 0003_sales_warranty
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0004_returns_exchange_repairs"
down_revision = "0003_sales_warranty"
branch_labels = None
depends_on = None

def upgrade():
    uuid = postgresql.UUID(as_uuid=True); dt = sa.DateTime(timezone=True); money = sa.Numeric(18,2); qty = sa.Numeric(18,3)
    op.create_table("repairs",
        sa.Column("id", uuid, primary_key=True), sa.Column("branch_id", uuid, sa.ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("repair_no", sa.String(40), unique=True, nullable=False), sa.Column("status", sa.String(40), nullable=False),
        sa.Column("device_brand", sa.String(100)), sa.Column("model", sa.String(150)), sa.Column("given_accessories", sa.Text()), sa.Column("special_note", sa.Text()),
        sa.Column("customer_id", uuid, sa.ForeignKey("customers.id", ondelete="RESTRICT")), sa.Column("customer_name", sa.String(150)), sa.Column("contact_no", sa.String(50)),
        sa.Column("date_in", dt, nullable=False), sa.Column("hand_over_date", sa.Date()), sa.Column("description_amount", sa.Text()), sa.Column("repair_invoice_ref", sa.String(100)),
        sa.Column("advance_payment", money, nullable=False, server_default="0"), sa.Column("total_amount", money, nullable=False, server_default="0"), sa.Column("labour_amount", money, nullable=False, server_default="0"),
        sa.Column("reported_fault", sa.Text()), sa.Column("estimated_amount", money), sa.Column("final_amount", money), sa.Column("warranty_period", sa.String(100)),
        sa.Column("authorized_by", uuid, sa.ForeignKey("users.id", ondelete="RESTRICT")), sa.Column("notes", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"), sa.Column("created_at", dt, nullable=False), sa.Column("updated_at", dt, nullable=False))
    op.create_index("ix_repairs_branch_status", "repairs", ["branch_id","status"]); op.create_index("ix_repairs_contact", "repairs", ["contact_no"])
    op.create_table("repair_parts",
        sa.Column("id", uuid, primary_key=True), sa.Column("repair_id", uuid, sa.ForeignKey("repairs.id", ondelete="RESTRICT"), nullable=False), sa.Column("item_id", uuid, sa.ForeignKey("items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", qty, nullable=False), sa.Column("charge_amount", money, nullable=False, server_default="0"), sa.Column("fifo_cost", money, nullable=False, server_default="0"), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("stock_movement_id", uuid, sa.ForeignKey("stock_movements.id", ondelete="RESTRICT")), sa.Column("notes", sa.Text()), sa.Column("version", sa.Integer(), nullable=False, server_default="1"), sa.Column("created_at", dt, nullable=False), sa.Column("updated_at", dt, nullable=False))
    op.create_table("repair_payments",
        sa.Column("id", uuid, primary_key=True), sa.Column("repair_id", uuid, sa.ForeignKey("repairs.id", ondelete="RESTRICT"), nullable=False), sa.Column("payment_method", sa.String(30), nullable=False), sa.Column("amount", money, nullable=False),
        sa.Column("payment_datetime", dt, nullable=False), sa.Column("reference", sa.String(150)), sa.Column("payment_type", sa.String(30), nullable=False), sa.Column("reversal_of_id", uuid), sa.Column("created_at", dt, nullable=False), sa.Column("updated_at", dt, nullable=False))
    op.create_index("ix_repair_payments_repair", "repair_payments", ["repair_id"])
    op.create_table("repair_warranties",
        sa.Column("id", uuid, primary_key=True), sa.Column("repair_id", uuid, sa.ForeignKey("repairs.id", ondelete="RESTRICT"), nullable=False), sa.Column("start_date", sa.Date(), nullable=False), sa.Column("expiry_date", sa.Date()), sa.Column("warranty_period", sa.String(100)), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"), sa.Column("created_at", dt, nullable=False), sa.Column("updated_at", dt, nullable=False))

def downgrade():
    for t in ["repair_warranties","repair_payments","repair_parts","repairs"]: op.drop_table(t)
