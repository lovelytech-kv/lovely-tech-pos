from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field


class UserListItemOut(BaseModel):
    user_id: UUID
    username: str
    display_name: str
    role: str
    role_id: UUID
    branch_id: UUID
    is_active: bool
    must_change_password: bool
    discount_limit_percent: Decimal
    version: int
    created_at: datetime | None = None
    last_login_at: datetime | None = None
    failed_login_count: int
    locked_until: datetime | None = None


class UserManagedListOut(BaseModel):
    items: list[UserListItemOut]
    total: int


class UserCreateIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=150)
    role: Literal['ADMIN', 'CASHIER']
    branch_id: UUID | None = None
    discount_limit_percent: Decimal = Field(default=Decimal('0'), ge=0, le=100)
    must_change_password: bool = True


class UserUpdateIn(BaseModel):
    version: int
    display_name: str | None = Field(default=None, min_length=1, max_length=150)
    discount_limit_percent: Decimal | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None
    must_change_password: bool | None = None


class UserPasswordResetIn(BaseModel):
    new_password: str = Field(min_length=8, max_length=200)