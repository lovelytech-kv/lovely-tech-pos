from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, Uuid, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin

class Customer(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "customers"
    name: Mapped[str | None] = mapped_column(String(150))
    contact_no: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (Index("ix_customers_contact", "contact_no"),)

class Sale(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "sales"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    invoice_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"))
    sale_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cashier_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    manual_invoice_ref: Mapped[str | None] = mapped_column(String(100))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    void_reason: Mapped[str | None] = mapped_column(Text)
    branch = relationship("Branch")
    customer = relationship("Customer")
    __table_args__ = (
        Index("ix_sales_branch_datetime", "branch_id", "sale_datetime"),
        Index("ix_sales_manual_ref", "manual_invoice_ref"),
    )

class SaleLine(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "sale_lines"
    sale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    serialized_unit_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("serialized_units.id", ondelete="RESTRICT"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18,3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    final_total: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    __table_args__ = (Index("ix_sale_lines_item", "item_id"),)

class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    sale_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("sales.id", ondelete="RESTRICT"))
    settlement_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    payment_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(150))
    __table_args__ = (Index("ix_payments_sale", "sale_id"), Index("ix_payments_datetime", "payment_datetime"))

class Return(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "returns"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    return_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    original_sale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False)
    cashier_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    return_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refund_total: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    return_charge: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="COMPLETED")
    reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (Index("ix_returns_sale", "original_sale_id"),)

class ReturnPayment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "return_payments"
    return_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("returns.id", ondelete="RESTRICT"), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    payment_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(150))
    idempotency_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    __table_args__ = (Index("ix_return_payments_return", "return_id"), Index("ix_return_payments_datetime", "payment_datetime"))

class ReturnLine(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "return_lines"
    return_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("returns.id", ondelete="RESTRICT"), nullable=False)
    original_sale_line_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sale_lines.id", ondelete="RESTRICT"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18,3), nullable=False)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    condition: Mapped[str] = mapped_column(String(20), nullable=False)  # GOOD / DAMAGED

class Exchange(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "exchanges"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    exchange_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    return_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("returns.id", ondelete="RESTRICT"), nullable=False)
    replacement_sale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False)
    difference_amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="COMPLETED")

class Repair(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "repairs"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    repair_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="RECEIVED")
    device_brand: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(150))
    given_accessories: Mapped[str | None] = mapped_column(Text)
    special_note: Mapped[str | None] = mapped_column(Text)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"))
    customer_name: Mapped[str | None] = mapped_column(String(150))
    contact_no: Mapped[str | None] = mapped_column(String(50))
    date_in: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hand_over_date: Mapped[date | None] = mapped_column(Date)
    description_amount: Mapped[str | None] = mapped_column(Text)
    repair_invoice_ref: Mapped[str | None] = mapped_column(String(100))
    advance_payment: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False, default=0)
    labour_amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False, default=0)
    reported_fault: Mapped[str | None] = mapped_column(Text)
    estimated_amount: Mapped[Decimal | None] = mapped_column(Numeric(18,2))
    final_amount: Mapped[Decimal | None] = mapped_column(Numeric(18,2))
    warranty_period: Mapped[str | None] = mapped_column(String(100))
    authorized_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (Index("ix_repairs_branch_status", "branch_id", "status"), Index("ix_repairs_contact", "contact_no"))

class RepairPart(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "repair_parts"
    repair_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("repairs.id", ondelete="RESTRICT"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18,3), nullable=False)
    charge_amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False, default=0)
    fifo_cost: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="USED")
    stock_movement_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("stock_movements.id", ondelete="RESTRICT"))
    notes: Mapped[str | None] = mapped_column(Text)

class RepairPayment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "repair_payments"
    repair_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("repairs.id", ondelete="RESTRICT"), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    payment_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(150))
    payment_type: Mapped[str] = mapped_column(String(30), nullable=False, default="RECEIPT")
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    proof_reference: Mapped[str | None] = mapped_column(String(150))
    proof_no: Mapped[str | None] = mapped_column(String(40), unique=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    __table_args__ = (Index("ix_repair_payments_repair", "repair_id"),)

class RepairWarranty(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "repair_warranties"
    repair_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("repairs.id", ondelete="RESTRICT"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    warranty_period: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")

class CreditSettlement(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "credit_settlements"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
    sale_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("sales.id", ondelete="RESTRICT"))
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    settlement_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    previous_outstanding: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    remaining_outstanding: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(150))
    proof_reference: Mapped[str | None] = mapped_column(String(150))
    proof_no: Mapped[str | None] = mapped_column(String(40), unique=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    __table_args__ = (Index("ix_credit_settlements_customer", "customer_id", "settlement_datetime"),)

class Expense(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "expenses"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("expense_categories.id", ondelete="RESTRICT"), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="APPROVED")
    entered_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))

class OtherIncome(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "other_income"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    income_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="APPROVED")
    entered_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
