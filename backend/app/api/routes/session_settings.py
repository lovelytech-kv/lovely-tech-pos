"""Admin-configurable session timeout settings."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.models.master import User
from app.services.session_settings import get_session_settings, save_session_settings

router = APIRouter(prefix='/session-settings', tags=['session-settings'])


class SessionSettingsIn(BaseModel):
    admin_minutes: int = Field(ge=0, le=720)      # 0 = disabled idle timeout
    cashier_minutes: int = Field(ge=0, le=720)
    admin_hours: int = Field(ge=0, le=8760)       # 0 = never expires
    cashier_hours: int = Field(ge=0, le=8760)


class SessionSettingsOut(BaseModel):
    admin_minutes: int
    cashier_minutes: int
    admin_hours: int
    cashier_hours: int


@router.get('', response_model=SessionSettingsOut)
def get_settings(
    user: User = Depends(require_permission('ADMIN_PANEL')),
    db: Session = Depends(db_session),
):
    return SessionSettingsOut(**get_session_settings(db))


@router.put('', response_model=SessionSettingsOut)
def update_settings(
    payload: SessionSettingsIn,
    user: User = Depends(require_permission('ADMIN_PANEL')),
    db: Session = Depends(db_session),
):
    try:
        result = save_session_settings(db, payload.model_dump(), user.id)
        db.commit()
        return SessionSettingsOut(**result)
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f'Failed to save session settings: {e}')