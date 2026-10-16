from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON, Uuid, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.db.session import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin

class ImportBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_batches"
    branch_id = Column(Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False)
    filename = Column(String(255), nullable=False)
    uploaded_by = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    status = Column(String(50), default="PENDING_APPROVAL", nullable=False)
    approved_by = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    rows = relationship("ImportStagingRow", back_populates="batch", cascade="all, delete-orphan")
    mappings = relationship("ImportMapping", back_populates="batch", cascade="all, delete-orphan")

class ImportStagingRow(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "import_staging_rows"
    batch_id = Column(Uuid(as_uuid=True), ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False)
    row_number = Column(Integer, nullable=False)
    row_type = Column(String(50), nullable=False)
    raw_data = Column(JSON, nullable=False)
    validation_status = Column(String(50), default="PENDING", nullable=False)
    error_details = Column(Text, nullable=True)
    reference_id = Column(Uuid(as_uuid=True), nullable=True)

    batch = relationship("ImportBatch", back_populates="rows")

class ImportMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_mappings"
    batch_id = Column(Uuid(as_uuid=True), ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False)
    import_type = Column(String(50), nullable=False)
    source_column = Column(String(255), nullable=False)
    target_field = Column(String(255), nullable=False)
    is_required = Column(String(10), default="false", nullable=False)
    transform_hint = Column(String(50), nullable=True)

    __table_args__ = (
        UniqueConstraint("batch_id", "source_column", name="uq_import_mapping_batch_source"),
        UniqueConstraint("batch_id", "target_field", name="uq_import_mapping_batch_target"),
    )

    batch = relationship("ImportBatch", back_populates="mappings")
