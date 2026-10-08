from __future__ import annotations
import hashlib, secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_session_factory
from app.models.auth import UserSession
from app.models.master import User, Permission, RolePermission

bearer = HTTPBearer(auto_error=False)

def db_session():
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def issue_session(db: Session, user: User) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    minutes = settings.session_timeout_admin_minutes if user.role.code.upper() == "ADMIN" else settings.session_timeout_cashier_minutes
    absolute_hours = settings.session_absolute_timeout_admin_hours if user.role.code.upper() == "ADMIN" else settings.session_absolute_timeout_cashier_hours
    expires = now + timedelta(hours=absolute_hours)
    raw = secrets.token_urlsafe(48)
    db.add(UserSession(user_id=user.id, token_hash=token_hash(raw), created_at=now, expires_at=expires, last_seen_at=now))
    return raw, expires

def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(db_session)) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    now = datetime.now(timezone.utc)
    session = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash(credentials.credentials)).with_for_update())
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or revoked")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    timeout_minutes = (
        settings.session_timeout_admin_minutes
        if user.role.code.upper() == "ADMIN"
        else settings.session_timeout_cashier_minutes
    )
    if session.last_seen_at + timedelta(minutes=timeout_minutes) <= now:
        session.revoked_at = now
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session locked due to inactivity")
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    session.last_seen_at = now
    db.commit()
    return user

def require_permission(code: str):
    def dependency(user: User = Depends(current_user), db: Session = Depends(db_session)) -> User:
        if user.role.code.upper() == "ADMIN":
            return user
        allowed = db.scalar(select(Permission.id).join(RolePermission, RolePermission.permission_id == Permission.id).where(RolePermission.role_id == user.role_id, Permission.code == code))
        if allowed is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission required: {code}")
        return user
    return dependency
