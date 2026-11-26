"""Admin-configurable session timeout settings."""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.models.master import User
from app.models.security import AuditLog
from app.security.reauth import require_admin_reauth
from app.services.session_settings import get_session_settings, save_session_settings

router = APIRouter(prefix='/session-settings', tags=['session-settings'])


class SessionSettingsIn(BaseModel):
    admin_minutes: int = Field(ge=1, le=720)      # zero (disabled idle) rejected
    cashier_minutes: int = Field(ge=1, le=720)
    admin_hours: int = Field(ge=1, le=8760)       # zero (never expires) rejected
    cashier_hours: int = Field(ge=1, le=8760)
    admin_password: str | None = None             # re-auth required to weaken timeouts


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
    require_admin_reauth(user=user, password=payload.admin_password, db=db, action='session settings change')
    try:
        before = get_session_settings(db)
        result = save_session_settings(db, payload.model_dump(exclude={'admin_password'}), user.id)
        db.add(AuditLog(
            branch_id=user.branch_id,
            actor_user_id=user.id,
            action_type='SESSION_SETTINGS_UPDATED',
            entity_type='SYSTEM_SETTINGS',
            entity_id=None,
            timestamp=datetime.now(timezone.utc),
            before_json=before,
            after_json=result,
        ))
        db.commit()
        return SessionSettingsOut(**result)
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f'Failed to save session settings: {e}')