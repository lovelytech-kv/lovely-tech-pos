import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin

class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_log"
    branch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    before_json: Mapped[dict | None] = mapped_column(JSON)
    after_json: Mapped[dict | None] = mapped_column(JSON)
    source_transaction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    context_json: Mapped[dict | None] = mapped_column(JSON)
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"), Index("ix_audit_actor_time", "actor_user_id", "timestamp"))

class IdempotencyKey(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "idempotency_keys"
    key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    request_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    response_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class RecordVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "record_versions"
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index("ix_record_versions_entity", "entity_type", "entity_id", "version", unique=True),)

class LoginEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "login_events"
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    username_attempted: Mapped[str] = mapped_column(String(80), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    context_json: Mapped[dict | None] = mapped_column(JSON)

class DocumentEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "document_events"
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)

class ApprovalRequest(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "approval_requests"
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    source_transaction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    requester_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[str | None] = mapped_column(Text)
    approval_action_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

class AdminRecoveryCode(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "admin_recovery_codes"
    code_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
