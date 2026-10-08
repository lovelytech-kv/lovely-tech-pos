from __future__ import annotations
import uuid
from datetime import date
from datetime import date, datetime
from decimal import Decimal
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, Uuid, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin

class ProductWarranty(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "product_warranties"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    sale_line_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("sale_lines.id", ondelete="RESTRICT"))
    serialized_unit_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("serialized_units.id", ondelete="RESTRICT"))
    warranty_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    warranty_type: Mapped[str] = mapped_column(String(30), nullable=False)
    duration_value: Mapped[int | None] = mapped_column()
    custom_rule: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    __table_args__ = (Index("ix_warranty_expiry_status", "expiry_date", "status"),)

class ManualWarrantyDocument(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "manual_warranty_documents"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    reference_no: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(150))
    item_description: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("branch_id", "reference_no", name="uq_manual_warranty_branch_reference"),)

class WarrantyDocumentEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "warranty_document_events"
    warranty_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("product_warranties.id", ondelete="RESTRICT"))
    manual_document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("manual_warranty_documents.id", ondelete="RESTRICT"))
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)  # ORIGINAL/REPRINT/DUPLICATE/RECOVERY
    actor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

class WarrantyClaim(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "warranty_claims"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    claim_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    product_warranty_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("product_warranties.id", ondelete="RESTRICT"))
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    admin_decision: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDING_ADMIN")
    supplier_process: Mapped[str | None] = mapped_column(String(40))
    holding_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18,3))
    replacement_outcome: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (Index("ix_warranty_claims_decision", "admin_decision"),)
