import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin

class Branch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "branches"
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roles"
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class Permission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True)
    permission_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("permissions.id", ondelete="RESTRICT"), primary_key=True)

class User(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discount_limit_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    role = relationship(Role)
    branch = relationship(Branch)
    __table_args__ = (Index("ix_users_branch_active", "branch_id", "is_active"),)

class Category(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "categories"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (UniqueConstraint("parent_id", "name", name="uq_categories_parent_name"),)

class ItemType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "item_types"
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_serialized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

class Item(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "items"
    item_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    compatible_models: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False)
    item_type_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("item_types.id", ondelete="RESTRICT"), nullable=False)
    master_sale_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    category = relationship(Category)
    item_type = relationship(ItemType)
    barcodes = relationship("ItemBarcode", back_populates="item", cascade="all, delete-orphan")
    __table_args__ = (
        CheckConstraint("master_sale_price IS NULL OR master_sale_price >= 0", name="ck_items_sale_price_nonnegative"),
        Index("ix_items_search", "description", "brand", "model"),
    )

class ItemBarcode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "item_barcodes"
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    barcode: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    item = relationship(Item, back_populates="barcodes")
    __table_args__ = (Index("ix_item_barcodes_item", "item_id"),)

class Variant(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "variants"
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[str] = mapped_column(String(120), nullable=False)
    item = relationship(Item)
    __table_args__ = (UniqueConstraint("item_id", "name", "value", name="uq_variants_item_name_value"),)

class WarrantyDefault(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "warranty_defaults"
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    warranty_type: Mapped[str] = mapped_column(String(30), nullable=False)
    duration_value: Mapped[int | None] = mapped_column(Integer)
    custom_rule: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

class Supplier(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "suppliers"
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    contact_no: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

class ExpenseCategory(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "expense_categories"
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

class TargetProgressSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "target_progress_snapshots"
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("targets.id", ondelete="RESTRICT"), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    target_version: Mapped[int] = mapped_column(Integer, nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    achieved_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    percentage: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    captured_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    __table_args__ = (UniqueConstraint("target_id", "target_version", name="uq_target_progress_snapshot_version"), Index("ix_target_snapshots_branch_period", "branch_id", "period_start", "period_end"))


class Target(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "targets"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    __table_args__ = (Index("ix_targets_branch_period", "branch_id", "period_start", "period_end"),)
