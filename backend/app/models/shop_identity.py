from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ShopIdentity(Base):
    __tablename__ = "shop_identity"
    __table_args__ = (
        CheckConstraint("identity_key = 'primary'", name="ck_shop_identity_singleton_key"),
        CheckConstraint("identity_version = 1", name="ck_shop_identity_version"),
    )

    identity_key: Mapped[str] = mapped_column(String(16), primary_key=True, default="primary")
    shop_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), unique=True, nullable=False)
    identity_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
