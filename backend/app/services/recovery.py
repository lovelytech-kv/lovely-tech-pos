from __future__ import annotations
import hashlib, secrets
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.master import User
from app.models.security import AuditLog
from app.security.passwords import hash_password, verify_password

class RecoveryError(ValueError): pass

def _hash_code(code:str)->str: return hashlib.sha256(code.encode()).hexdigest()

class RecoveryService:
    def __init__(self, session:Session): self.session=session
    def create_offline_admin_code(self, *, admin_user_id, actor_user_id):
        # Code is displayed exactly once to the authorized admin during setup.
        from app.models.security import AdminRecoveryCode
        code='LT-' + secrets.token_hex(8).upper()
        row=AdminRecoveryCode(code_hash=_hash_code(code),created_at=datetime.now(timezone.utc),created_by=actor_user_id)
        self.session.add(row); self.session.add(AuditLog(actor_user_id=actor_user_id,action_type='RECOVERY_CODE_CREATED',entity_type='USER',entity_id=admin_user_id,timestamp=datetime.now(timezone.utc),context_json={'one_time':True})); self.session.flush()
        return code
    def recover_admin(self, *, user:User, recovery_code:str, new_password:str):
        from app.models.security import AdminRecoveryCode
        if not user.is_active: raise RecoveryError('User is inactive')
        row=self.session.scalar(select(AdminRecoveryCode).where(AdminRecoveryCode.code_hash==_hash_code(recovery_code),AdminRecoveryCode.used_at.is_(None)).with_for_update())
        if not row: raise RecoveryError('Invalid or already-used recovery code')
        user.password_hash=hash_password(new_password); user.must_change_password=False; row.used_at=datetime.now(timezone.utc); row.used_by=user.id
        self.session.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='ADMIN_PASSWORD_RECOVERY',entity_type='USER',entity_id=user.id,timestamp=datetime.now(timezone.utc),context_json={'recovery_code_used':True})); self.session.flush()


    def reset_cashier_by_admin(self, *, target_user: User, admin_user: User, admin_password: str, new_password: str):
        if admin_user.role.code.upper() != 'ADMIN':
            raise RecoveryError('Admin verification is required')
        if target_user.branch_id != admin_user.branch_id:
            raise RecoveryError('User belongs to another branch')
        if target_user.id == admin_user.id:
            raise RecoveryError('Use offline admin recovery for the admin account')
        if not verify_password(admin_user.password_hash, admin_password):
            raise RecoveryError('Admin verification failed')
        if not target_user.is_active:
            raise RecoveryError('Target user is inactive')
        target_user.password_hash = hash_password(new_password)
        target_user.must_change_password = True
        target_user.failed_login_count = 0
        target_user.locked_until = None
        now = datetime.now(timezone.utc)
        self.session.add(AuditLog(branch_id=admin_user.branch_id, actor_user_id=admin_user.id, action_type='CASHIER_PASSWORD_RESET', entity_type='USER', entity_id=target_user.id, timestamp=now, context_json={'forced_change':True}))
        self.session.flush()
