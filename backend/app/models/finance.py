from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin

class DaySession(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "day_sessions"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN")
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False, default=0)
    opening_note: Mapped[str | None] = mapped_column(Text)
    opening_denominations: Mapped[dict | None] = mapped_column(JSON)
    shift_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shift_end_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    __table_args__ = (Index("ix_day_sessions_branch_date", "branch_id", "business_date"),)

class DayEnd(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "day_ends"
    day_session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("day_sessions.id", ondelete="RESTRICT"), nullable=False)
    expected_cash: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    actual_cash: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    difference: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    reload_total: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False, default=0)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    actual_denominations: Mapped[dict | None] = mapped_column(JSON)
    completed_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class ReloadEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reload_entries"
    day_session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("day_sessions.id", ondelete="RESTRICT"), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    entered_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

class OtherCashIn(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "other_cash_in"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    day_session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("day_sessions.id", ondelete="RESTRICT"))
    transaction_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    entered_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
