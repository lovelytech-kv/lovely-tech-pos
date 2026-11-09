from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.models.common import UUIDPrimaryKeyMixin


class ShopIdentity(UUIDPrimaryKeyMixin, Base):
    """Single-row table holding the shop's permanent UUID + display name.

    `shop_uuid` is generated once at seed time and NEVER regenerated.
    `shop_name` mirrors branches.name (kept in sync from setup + admin update).
    """
    __tablename__ = "shop_identity"
    shop_uuid: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), unique=True, nullable=False)
    shop_name: Mapped[str | None] = mapped_column(String(150))
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    upgraded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))