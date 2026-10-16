from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal

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
