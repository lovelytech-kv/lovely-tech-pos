from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SetupShopIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    address: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=120)


class SetupAdminIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=150)


class SetupInitializeIn(BaseModel):
    shop: SetupShopIn
    admin: SetupAdminIn


class SetupStatusOut(BaseModel):
    is_initialized: bool
    reason: Literal["ready", "no_users", "no_admin_user", "no_branch_profile"]
    user_count: int
    has_admin: bool


class SetupInitializeOut(BaseModel):
    success: bool
    branch_id: UUID
    admin_user_id: UUID
    username: str