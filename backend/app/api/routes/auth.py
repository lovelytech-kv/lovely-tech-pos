from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import db_session, issue_session, token_hash, current_user
from app.models.master import User
from app.models.security import LoginEvent
from app.schemas.api import LoginIn, LoginOut, PasswordChangeIn, AdminRecoveryIn
from app.security.passwords import verify_password, hash_password

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, db: Session = Depends(db_session)):
    user = db.scalar(select(User).where(User.username == payload.username))
    now = datetime.now(timezone.utc)
    if user is None or not user.is_active or (user.locked_until and user.locked_until > now) or not verify_password(user.password_hash, payload.password):
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= 5:
                from datetime import timedelta
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
    # Revoke all sessions for this user: safe default for cashier/admin logout.
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
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    now = datetime.now(timezone.utc)
    db.add(LoginEvent(username_attempted=user.username, user_id=user.id, event_type='PASSWORD_CHANGED', occurred_at=now))
    db.commit()
    return {'status':'password_changed','must_change_password':False}
