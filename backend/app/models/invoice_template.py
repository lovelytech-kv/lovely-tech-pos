from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import UUIDPrimaryKeyMixin


class InvoiceTemplate(UUIDPrimaryKeyMixin, Base):
    """Receipt / invoice layout configuration.

    The branded "Software by Lovely Tech · <shop phone>" line is intentionally
    NOT stored here: the receipt builder appends it after all user content and
    it cannot be removed through the API.
    """
    __tablename__ = 'invoice_templates'

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    paper_size: Mapped[str] = mapped_column(String(10), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Header
    show_logo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    header_text: Mapped[str | None] = mapped_column(Text)
    show_address: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_phone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Body
    show_customer_name: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_customer_phone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_item_description: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_item_code: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_unit_price: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_warranty_info: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_repair_details: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_payment_method: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_cashier: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_customer_notes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Thermal 80mm monochrome logo (1-bit conversion happens at print time)
    logo_monochrome: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Footer (user content — always printed BEFORE the locked branding line)
    footer_text: Mapped[str | None] = mapped_column(Text)
    warranty_terms: Mapped[str | None] = mapped_column(Text)
    show_footer_note: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'),
    )
