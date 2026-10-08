from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

class ItemCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_code: str | None = Field(default=None, max_length=30)
    description: str = Field(min_length=1, max_length=255)
    category_id: UUID
    item_type_id: UUID
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    master_sale_price: Decimal | None = Field(default=None, ge=0)
    barcode: str | None = Field(default=None, max_length=100)

class ItemUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=1, max_length=255)
    category_id: UUID
    item_type_id: UUID
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    master_sale_price: Decimal | None = Field(default=None, ge=0)
    version: int = Field(ge=1)

class BarcodeIn(BaseModel):
    barcode: str = Field(min_length=1, max_length=100)
    is_primary: bool = False


class WarrantyDefaultIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    warranty_type: str
    duration_value: int | None = Field(default=None, ge=1)
    custom_rule: str | None = None
