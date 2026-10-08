from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin

class BackupPoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = 'backup_points'
    branch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('branches.id', ondelete='RESTRICT'))
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    storage_target: Mapped[str] = mapped_column(String(300), nullable=False)
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(128))
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT'))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    sync_state: Mapped[str] = mapped_column(String(30), nullable=False, default='LOCAL_ONLY')
    remote_path: Mapped[str | None] = mapped_column(String(500))
    __table_args__ = (Index('ix_backup_points_state', 'state', 'verified_at'), Index('ix_backup_points_sync_state','branch_id','sync_state','verified_at'),)

class RestoreEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = 'restore_events'
    branch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('branches.id', ondelete='RESTRICT'))
    backup_point_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('backup_points.id', ondelete='RESTRICT'))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT'))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
