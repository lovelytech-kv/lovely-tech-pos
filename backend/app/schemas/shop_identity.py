"""Shop identity schemas."""
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class ShopIdentityOut(BaseModel):
    shop_uuid: UUID
    shop_name: str
    schema_version: int
    created_at: datetime


class ShopNameUpdateIn(BaseModel):
    shop_name: str = Field(min_length=1, max_length=150)