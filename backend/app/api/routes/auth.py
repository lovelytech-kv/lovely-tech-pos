from datetime import datetime, timezone, timedelta
import hashlib, secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.api.deps import db_session, issue_session, token_hash, current_user
from app.core.config import settings
from app.models.master import User
from app.models.security import LoginEvent, AdminRecoveryCode, PasswordResetToken, AuditLog
from app.schemas.api import LoginIn, LoginOut, PasswordChangeIn, AdminRecoveryIn, ReauthIn
from pydantic import BaseModel
from app.schemas.recovery import (
    ForgotPasswordVerifyIn,
    ForgotPasswordVerifyOut,
    ResetPasswordWithTokenIn,
    ResetPasswordWithTokenOut,
    RecoveryCodesResponse,
    RecoveryStatusOut,
    EmergencyResetIn,
)
from app.security.passwords import verify_password, hash_password
from app.security.reauth import require_admin_reauth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, db: Session = Depends(db_session)):
    user = db.scalar(select(User).where(User.username == payload.username))
    now = datetime.now(timezone.utc)
    if user is None or not user.is_active or (user.locked_until and user.locked_until > now) or not verify_password(user.password_hash, payload.password):
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= 5:
                user.locked_until = now + timedelta(minutes=15)
        db.add(LoginEvent(username_attempted=payload.username, user_id=user.id if user else None, event_type="LOGIN_FAILED", occurred_at=now))
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid username or password")
    user.failed_login_count = 0
    user.locked_until = None
    token, expires = issue_session(db, user)
    db.add(LoginEvent(username_attempted=payload.username, user_id=user.id, event_type="LOGIN_SUCCESS", occurred_at=now))
    db.commit()
    return LoginOut(access_token=token, expires_at=expires, user_id=user.id, username=user.username, display_name=user.display_name, role=user.role.code, branch_id=user.branch_id, must_change_password=user.must_change_password)


@router.post("/logout")
def logout(user=Depends(current_user), db: Session = Depends(db_session)):
    from app.models.auth import UserSession
    from sqlalchemy import update
    now = datetime.now(timezone.utc)
    db.execute(update(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None)).values(revoked_at=now))
    db.add(LoginEvent(username_attempted=user.username, user_id=user.id, event_type="LOGOUT", occurred_at=now))
    db.commit()
    return {"status": "logged_out"}


@router.get("/me", response_model=LoginOut)
def me(user=Depends(current_user)):
    return LoginOut(access_token="", expires_at=datetime.now(timezone.utc), user_id=user.id, username=user.username, display_name=user.display_name, role=user.role.code, branch_id=user.branch_id, must_change_password=user.must_change_password)


@router.post('/admin/recovery-code')
def create_recovery_code(user=Depends(current_user), db: Session=Depends(db_session)):
    if user.role.code.upper() != 'ADMIN': raise HTTPException(403,'Admin only')
    from app.services.recovery import RecoveryService
    code=RecoveryService(db).create_offline_admin_code(admin_user_id=user.id,actor_user_id=user.id); db.commit(); return {'recovery_code':code}


@router.post('/admin/recover')
def recover_admin(payload: AdminRecoveryIn, db: Session = Depends(db_session)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or user.role.code.upper() != 'ADMIN':
        raise HTTPException(400, 'Invalid recovery credentials')
    from app.services.recovery import RecoveryService, RecoveryError
    try:
        RecoveryService(db).recover_admin(user=user, recovery_code=payload.recovery_code, new_password=payload.new_password)
        from app.models.auth import UserSession
        now = datetime.now(timezone.utc)
        db.query(UserSession).filter(UserSession.user_id == user.id, UserSession.revoked_at.is_(None)).update({UserSession.revoked_at: now}, synchronize_session=False)
        db.add(LoginEvent(username_attempted=user.username, user_id=user.id, event_type='ADMIN_RECOVERY_SUCCESS', occurred_at=now))
        db.commit()
    except RecoveryError as exc:
        db.rollback()
        raise HTTPException(400, str(exc))
    return {'status':'recovered','must_change_password':False}


@router.post('/change-password')
def change_password(payload: PasswordChangeIn, user=Depends(current_user), db: Session=Depends(db_session)):
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(401, 'Current password is incorrect')
    if payload.new_password == payload.current_password:
        raise HTTPException(400, 'New password must be different from the current password')
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    now = datetime.now(timezone.utc)
    db.add(LoginEvent(username_attempted=user.username, user_id=user.id, event_type='PASSWORD_CHANGED', occurred_at=now))
    db.commit()
    return {'status':'password_changed','must_change_password':False}


# ============ CHUNK 11 — PASSWORD RECOVERY ============

RESET_TOKEN_TTL_MINUTES = 10


def _is_localhost(request: Request) -> bool:
    if request.client is None:
        return False
    host = request.client.host
    return host in ('127.0.0.1', '::1', 'localhost')


@router.post('/forgot-password-verify', response_model=ForgotPasswordVerifyOut)
def forgot_password_verify(payload: ForgotPasswordVerifyIn, request: Request, db: Session = Depends(db_session)):
    """Verify a one-time recovery code and issue a short-lived reset token."""
    from app.services.recovery import RecoveryService, RecoveryError
    try:
        result = RecoveryService(db).verify_recovery_code(
            username=payload.username.strip(),
            code=payload.recovery_code.strip(),
        )
    except RecoveryError as exc:
        db.rollback()
        raise HTTPException(429, str(exc))
    except Exception:
        db.rollback()
        raise

    if not result.get('valid'):
        db.commit()
        raise HTTPException(400, 'Invalid username or recovery code')

    # Generate single-use reset token (10 min)
    raw_token = secrets.token_urlsafe(32)
    token_hash_val = hashlib.sha256(raw_token.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    db.add(PasswordResetToken(
        user_id=result['user_id'],
        token_hash=token_hash_val,
        created_at=now,
        expires_at=now + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
    ))
    db.commit()
    return ForgotPasswordVerifyOut(valid=True, reset_token=raw_token)


@router.post('/reset-password-with-token', response_model=ResetPasswordWithTokenOut)
def reset_password_with_token(payload: ResetPasswordWithTokenIn, db: Session = Depends(db_session)):
    """Use a valid reset token to set a new password. Token is single-use, 10 min TTL."""
    token_hash_val = hashlib.sha256(payload.reset_token.encode()).hexdigest()
    now = datetime.now(timezone.utc)

    token = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash_val,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        ).with_for_update()
    )
    if token is None:
        raise HTTPException(400, 'Invalid or expired reset token')

    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(400, 'User not found')

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.failed_login_count = 0
    user.locked_until = None

    token.used_at = now
    db.add(LoginEvent(username_attempted=user.username, user_id=user.id, event_type='PASSWORD_RESET_VIA_RECOVERY', occurred_at=now))
    db.commit()
    return ResetPasswordWithTokenOut(success=True)


@router.post('/emergency-reset')
def emergency_reset(payload: EmergencyResetIn, request: Request, db: Session = Depends(db_session)):
    """Localhost-only emergency admin password reset.

    Requires POS_EMERGENCY_KEY in backend/.env. If not configured → 501.
    Only works from the server machine (127.0.0.1 / ::1).
    """
    if not settings.pos_emergency_key:
        raise HTTPException(501, 'Emergency reset not configured. Set POS_EMERGENCY_KEY in backend/.env')

    if not _is_localhost(request):
        client_ip = request.client.host if request.client else 'unknown'
        raise HTTPException(403, f'Emergency reset only available from server machine (localhost). Current IP: {client_ip}')

    if payload.superuser_key != settings.pos_emergency_key:
        raise HTTPException(400, 'Invalid superuser key')

    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None:
        raise HTTPException(404, 'User not found')
    if user.role.code.upper() != 'ADMIN':
        raise HTTPException(400, 'Emergency reset only allowed for admin accounts')

    now = datetime.now(timezone.utc)
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = True
    user.failed_login_count = 0
    user.locked_until = None

    from app.models.auth import UserSession
    from sqlalchemy import update as _upd
    db.execute(_upd(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None)).values(revoked_at=now))

    db.add(LoginEvent(username_attempted=user.username, user_id=user.id, event_type='EMERGENCY_LOCALHOST_RESET', occurred_at=now))
    db.add(AuditLog(
        branch_id=user.branch_id,
        actor_user_id=user.id,
        action_type='EMERGENCY_LOCALHOST_RESET',
        entity_type='USER',
        entity_id=user.id,
        timestamp=now,
        context_json={'client_ip': request.client.host if request.client else None},
    ))
    db.commit()
    return {'success': True}


class AdminReauthBody(BaseModel):
    admin_password: str | None = None


@router.post('/admin/recovery-codes/regenerate', response_model=RecoveryCodesResponse)
def admin_regenerate_recovery_codes(
    body: AdminReauthBody | None = None,
    admin_password: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(db_session),
):
    if user.role.code.upper() != 'ADMIN':
        raise HTTPException(403, 'Admin only')
    # Accept password from body OR query param (body preferred, avoids URL encoding issues)
    pwd = (body.admin_password if body else None) or admin_password
    require_admin_reauth(user=user, password=pwd, db=db, action='recovery code regeneration')
    from app.services.recovery import RecoveryService
    try:
        codes = RecoveryService(db).generate_recovery_codes(
            user_id=user.id,
            actor_user_id=user.id,
            count=8,
        )
        db.commit()
        return RecoveryCodesResponse(recovery_codes=codes)
    except Exception:
        db.rollback()
        raise


@router.post('/admin/recovery-codes/remaining', response_model=RecoveryStatusOut)
def admin_recovery_codes_remaining(
    user: User = Depends(current_user),
    db: Session = Depends(db_session),
):
    if user.role.code.upper() != 'ADMIN':
        raise HTTPException(403, 'Admin only')

    total = db.scalar(
        select(func.count()).select_from(AdminRecoveryCode).where(
            AdminRecoveryCode.created_by == user.id,
            AdminRecoveryCode.revoked_at.is_(None),
        )
    ) or 0
    remaining = db.scalar(
        select(func.count()).select_from(AdminRecoveryCode).where(
            AdminRecoveryCode.created_by == user.id,
            AdminRecoveryCode.used_at.is_(None),
            AdminRecoveryCode.revoked_at.is_(None),
        )
    ) or 0
    last_gen = db.scalar(
        select(func.max(AdminRecoveryCode.created_at)).where(AdminRecoveryCode.created_by == user.id)
    )
    return RecoveryStatusOut(total=int(total), remaining=int(remaining), last_generated_at=last_gen)