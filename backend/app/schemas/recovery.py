from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


class ForgotPasswordVerifyIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    recovery_code: str = Field(min_length=8, max_length=64)


class ForgotPasswordVerifyOut(BaseModel):
    valid: bool
    reset_token: str | None = None


class ResetPasswordWithTokenIn(BaseModel):
    reset_token: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=200)


class ResetPasswordWithTokenOut(BaseModel):
    success: bool


class RecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


class RecoveryStatusOut(BaseModel):
    total: int
    remaining: int
    last_generated_at: datetime | None = None


class EmergencyResetIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    new_password: str = Field(min_length=8, max_length=200)
    superuser_key: str = Field(min_length=1, max_length=200)