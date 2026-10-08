from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

class PurchaseLineCreateIn(BaseModel):
    item_id: UUID
    quantity: Decimal = Field(gt=0)
    line_date: date | None = None
    notes: str | None = None

class PurchaseCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purchase_date: date
    payment_method: Literal["CASH", "CARD", "ONLINE"] = "CASH"
    lines: list[PurchaseLineCreateIn] = Field(min_length=1)
    reference_no: str | None = Field(default=None, max_length=100)
    supplier_id: UUID | None = None
    notes: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=120)

class PurchaseAdminEditIn(BaseModel):
    supplier_id: UUID | None = None
    reference_no: str | None = Field(default=None, max_length=100)
    purchase_date: date | None = None
    notes: str | None = None


class PurchaseHistoryLineOut(BaseModel):
    version: int
    purchase_version: int
    purchase_id: UUID
    purchase_line_id: UUID
    purchase_date: date
    line_date: date
    reference_no: str | None
    supplier_id: UUID | None
    supplier_name: str | None
    item_id: UUID
    item_code: str
    item_description: str
    quantity: Decimal
    unit_cost: Decimal | None
    payment_method: str
    status: str
