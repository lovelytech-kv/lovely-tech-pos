from __future__ import annotations
from datetime import datetime
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.models.common import UUIDPrimaryKeyMixin


class MachineIdentity(UUIDPrimaryKeyMixin, Base):
    """Single-row table describing this machine's role (SERVER or CLIENT)."""
    __tablename__ = "machine_identity"
    machine_role: Mapped[str] = mapped_column(String(10), nullable=False, default='SERVER')
    machine_name: Mapped[str | None] = mapped_column(String(100))
    server_url: Mapped[str | None] = mapped_column(String(255))
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))