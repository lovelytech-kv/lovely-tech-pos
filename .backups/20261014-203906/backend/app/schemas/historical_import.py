from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from uuid import UUID

class ImportItemRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    item_code: str = Field(alias="ITEM CODE")
    description: str = Field(alias="DESCRIPTION")
    category: Optional[str] = Field(None, alias="CATEGORY 1")
    brand: Optional[str] = Field(None, alias="Brand")
    warranty: Optional[str] = Field(None, alias="WARRANTY")
    sale_price: Optional[Decimal] = Field(None, alias="SALE PRICE")

class ImportPurchaseRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    date: datetime = Field(alias="DATE")
    item_code: str = Field(alias="ITEM CODE")
    unit_price: Decimal = Field(alias="UNIT PRICE")
    quantity: int = Field(alias="QUANTITY")

class ImportSaleRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    date: datetime = Field(alias="DATE")
    item_code: str = Field(alias="ITEM CODE")
    sale_price: Decimal = Field(alias="SALE PRICE")
    quantity: int = Field(alias="QUANTITY")

SCHEMA_FIELD_MAP = {
    "ITEM": {
        "required": ["item_code", "description"],
        "optional": ["category", "brand", "warranty", "sale_price"],
        "aliases": {
            "ITEM CODE": "item_code",
            "DESCRIPTION": "description",
            "CATEGORY 1": "category",
            "Brand": "brand",
            "WARRANTY": "warranty",
            "SALE PRICE": "sale_price",
        }
    },
    "PURCHASE": {
        "required": ["date", "item_code", "unit_price", "quantity"],
        "optional": [],
        "aliases": {
            "DATE": "date",
            "ITEM CODE": "item_code",
            "UNIT PRICE": "unit_price",
            "QUANTITY": "quantity",
        }
    },
    "SALE": {
        "required": ["date", "item_code", "sale_price", "quantity"],
        "optional": [],
        "aliases": {
            "DATE": "date",
            "ITEM CODE": "item_code",
            "SALE PRICE": "sale_price",
            "QUANTITY": "quantity",
        }
    },
}

class ImportMappingCreate(BaseModel):
    source_column: str = Field(..., min_length=1, max_length=255)
    target_field: str = Field(..., min_length=1, max_length=255)
    is_required: bool = Field(default=False)
    transform_hint: Optional[str] = Field(None, max_length=50)

class ImportMappingUpdate(BaseModel):
    target_field: Optional[str] = Field(None, min_length=1, max_length=255)
    is_required: Optional[bool] = None
    transform_hint: Optional[str] = Field(None, max_length=50)

class ImportMappingResponse(BaseModel):
    id: UUID
    batch_id: UUID
    import_type: str
    source_column: str
    target_field: str
    is_required: bool
    transform_hint: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ImportMappingBulkCreate(BaseModel):
    mappings: List[ImportMappingCreate]

class ImportMappingBulkResponse(BaseModel):
    mappings: List[ImportMappingResponse]
    warnings: List[str] = []
