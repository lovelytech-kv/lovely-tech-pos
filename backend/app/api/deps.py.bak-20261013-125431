from __future__ import annotations
import hashlib, secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_session_factory
from app.core.shop_identity import (
    ShopIdentityError,
    ShopIdentityStatus,
    inspect_shop_identity,
)
from app.core.restore_state import RestoreState, RestoreStateError, ensure_restore_state
from app.models.auth import UserSession
from app.models.master import User, Permission, RolePermission

bearer = HTTPBearer(auto_error=False)

_SHOP_IDENTITY_GATE_EXEMPT_MUTATIONS = {
    ("POST", "/api/v1/backup/create"),
    ("POST", "/api/v1/backup/verify/{backup_id}"),
    ("POST", "/api/v1/backup/restore/{backup_id}"),
    ("POST", "/api/v1/backup/sync/{backup_id}"),
    ("POST", "/api/v1/reports/sales-summary"),
    ("POST", "/api/v1/reports/target-progress"),
    ("POST", "/api/v1/reports/target-history"),
    ("POST", "/api/v1/reports/cashiers"),
    ("POST", "/api/v1/reports/cash-in-hands"),
    ("POST", "/api/v1/reports/comparison"),
    ("POST", "/api/v1/reports/stock-age"),
    ("POST", "/api/v1/reports/purchases"),
    ("POST", "/api/v1/reports/repairs"),
    ("POST", "/api/v1/reports/warranty"),
    ("POST", "/api/v1/reports/cash-drawer"),
    ("POST", "/api/v1/reports/export/{report_type}/{file_format}"),
}
_SHOP_IDENTITY_GATE_ERROR = (
    "Shop identity is not established; business writes are disabled."
)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _require_shop_identity_for_write(db: Session, request: Request) -> None:
    if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return

    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    request_method = request.method.upper()
    normalized_route_path = (
        route_path
        if route_path.startswith("/api/v1/")
        else f"/api/v1{route_path}"
    )
    if (request_method, normalized_route_path) in _SHOP_IDENTITY_GATE_EXEMPT_MUTATIONS:
        return

    try:
        restore_state = ensure_restore_state(settings.backup_root)
    except RestoreStateError as exc:
        raise HTTPException(
            status_code=409,
            detail="Restore recovery state is unavailable; business writes are disabled.",
        ) from exc
    if restore_state.state is not RestoreState.READY:
        raise HTTPException(
            status_code=409,
            detail="Restore recovery is incomplete; business writes are disabled.",
        )

    try:
        identity = inspect_shop_identity(db)
    except ShopIdentityError as exc:
        raise HTTPException(status_code=409, detail=_SHOP_IDENTITY_GATE_ERROR) from exc
    if identity.status is not ShopIdentityStatus.PRESENT or identity.shop_id is None:
        raise HTTPException(status_code=409, detail=_SHOP_IDENTITY_GATE_ERROR)


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
    if session is None or session.revoked_at is not None or _as_utc(session.expires_at) <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or revoked")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    timeout_minutes = (
        settings.session_timeout_admin_minutes
        if user.role.code.upper() == "ADMIN"
        else settings.session_timeout_cashier_minutes
    )
    if _as_utc(session.last_seen_at) + timedelta(minutes=timeout_minutes) <= now:
        session.revoked_at = now
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session locked due to inactivity")
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    session.last_seen_at = now
    db.commit()
    return user

def require_permission(code: str):
    def dependency(
        request: Request,
        user: User = Depends(current_user),
        db: Session = Depends(db_session),
    ) -> User:
        if user.role.code.upper() != "ADMIN":
            allowed = db.scalar(select(Permission.id).join(RolePermission, RolePermission.permission_id == Permission.id).where(RolePermission.role_id == user.role_id, Permission.code == code))
            if allowed is None:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission required: {code}")
        _require_shop_identity_for_write(db, request)
        return user
    return dependency
