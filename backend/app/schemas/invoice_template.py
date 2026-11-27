from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PaperSize = Literal['80mm', 'A4']


class InvoiceTemplateCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str = Field(min_length=1, max_length=100)
    paper_size: PaperSize
    is_active: bool = True

    show_logo: bool = True
    header_text: str | None = Field(default=None, max_length=200)
    show_address: bool = True
    show_phone: bool = True
    show_email: bool = False

    show_customer_name: bool = True
    show_customer_phone: bool = True
    show_item_description: bool = True
    show_item_code: bool = True
    show_unit_price: bool = True
    show_warranty_info: bool = True
    show_repair_details: bool = True
    show_payment_method: bool = False
    show_cashier: bool = False
    show_customer_notes: bool = False
    logo_monochrome: bool = False

    footer_text: str | None = Field(default=None, max_length=500)
    warranty_terms: str | None = Field(default=None, max_length=2000)
    show_footer_note: bool = True


class InvoiceTemplateUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str | None = Field(default=None, min_length=1, max_length=100)
    paper_size: PaperSize | None = None
    is_active: bool | None = None

    show_logo: bool | None = None
    header_text: str | None = Field(default=None, max_length=200)
    show_address: bool | None = None
    show_phone: bool | None = None
    show_email: bool | None = None

    show_customer_name: bool | None = None
    show_customer_phone: bool | None = None
    show_item_description: bool | None = None
    show_item_code: bool | None = None
    show_unit_price: bool | None = None
    show_warranty_info: bool | None = None
    show_repair_details: bool | None = None
    show_payment_method: bool | None = None
    show_cashier: bool | None = None
    show_customer_notes: bool | None = None
    logo_monochrome: bool | None = None

    footer_text: str | None = Field(default=None, max_length=500)
    warranty_terms: str | None = Field(default=None, max_length=2000)
    show_footer_note: bool | None = None


class InvoiceTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    paper_size: PaperSize
    is_default: bool
    is_active: bool

    show_logo: bool
    header_text: str | None = None
    show_address: bool
    show_phone: bool
    show_email: bool

    show_customer_name: bool
    show_customer_phone: bool
    show_item_description: bool
    show_item_code: bool
    show_unit_price: bool
    show_warranty_info: bool
    show_repair_details: bool
    show_payment_method: bool
    show_cashier: bool
    show_customer_notes: bool
    logo_monochrome: bool

    footer_text: str | None = None
    warranty_terms: str | None = None
    show_footer_note: bool

    created_at: datetime
    updated_at: datetime
    created_by: UUID | None = None
