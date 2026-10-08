from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.master import User
from app.security.passwords import verify_password


def require_admin_reauth(*, user: User, password: str | None, db: Session, action: str) -> None:
    if user.role.code.upper() != "ADMIN":
        raise HTTPException(403, "Admin only")
    if not settings.critical_reauth_required:
        return
    if not password or not verify_password(user.password_hash, password):
        raise HTTPException(401, f"Admin re-authentication required for {action}")
