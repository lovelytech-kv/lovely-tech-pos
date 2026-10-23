import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin

class Purchase(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "purchases"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    reference_no: Mapped[str | None] = mapped_column(String(100))
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"))
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_COST")
    payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)  # legacy: purchases no longer record a payment method (Req. 08)
    notes: Mapped[str | None] = mapped_column(Text)
    branch = relationship("Branch")
    supplier = relationship("Supplier")
    __table_args__ = (Index("ix_purchases_branch_date", "branch_id", "purchase_date"), Index("ix_purchases_pending_cost", "status"))

class PurchaseLine(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "purchase_lines"
    purchase_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("purchases.id", ondelete="RESTRICT"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    line_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (Index("ix_purchase_lines_item", "item_id"),)

class PurchaseLot(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "purchase_lots"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    purchase_line_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("purchase_lines.id", ondelete="RESTRICT"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    original_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    lot_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    __table_args__ = (Index("ix_purchase_lots_fifo", "branch_id", "item_id", "lot_date", "created_at"),)

class StockMovement(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stock_movements"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (Index("ix_stock_movements_item_date", "branch_id", "item_id", "occurred_at"), Index("ix_stock_movements_source", "source_type", "source_id"))

class FifoAllocation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "fifo_allocations"
    stock_movement_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("stock_movements.id", ondelete="RESTRICT"), nullable=False)
    purchase_lot_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("purchase_lots.id", ondelete="RESTRICT"))
    allocated_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    allocated_unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    allocation_status: Mapped[str] = mapped_column(String(30), nullable=False, default="ALLOCATED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index("ix_fifo_allocations_lot", "purchase_lot_id"), Index("ix_fifo_allocations_movement", "stock_movement_id"))

class StockAdjustment(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "stock_adjustments"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))

class DamageLossRecord(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "damage_loss_records"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(50))
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    review_status: Mapped[str] = mapped_column(String(30), nullable=False, default="APPROVED")
    __table_args__ = (Index("ix_damage_loss_review_status", "branch_id", "review_status", "created_at"),)

class WarrantyHolding(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "warranty_holdings"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    warranty_claim_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="HELD")

class SerializedUnit(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "serialized_units"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="IN_STOCK")
    purchase_lot_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("purchase_lots.id", ondelete="RESTRICT"))
    __table_args__ = (UniqueConstraint("branch_id", "serial_number", name="uq_serialized_units_branch_serial"), Index("ix_serialized_units_item", "item_id"))
