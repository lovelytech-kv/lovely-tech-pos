from __future__ import annotations
import hashlib, secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.master import User
from app.models.security import AuditLog
from app.security.passwords import hash_password, verify_password

# 32-char unambiguous alphabet (no 0/O/1/I/L)
_CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'


def _generate_recovery_code() -> str:
    """Format: XXXX-XXXX-XXXX (12 base32 chars, 60 bits of entropy)."""
    return '-'.join(
        ''.join(secrets.choice(_CODE_ALPHABET) for _ in range(4))
        for _ in range(3)
    )

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
        row=self.session.scalar(select(AdminRecoveryCode).where(AdminRecoveryCode.code_hash==_hash_code(recovery_code.strip().upper()),AdminRecoveryCode.used_at.is_(None),AdminRecoveryCode.revoked_at.is_(None)).with_for_update())
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
    def generate_recovery_codes(self, *, user_id, actor_user_id, count: int = 8) -> list[str]:
        """Generate `count` new recovery codes, revoking all previous unused codes.

        Returns plaintext codes — caller must show them ONCE.
        """
        from app.models.security import AdminRecoveryCode
        now = datetime.now(timezone.utc)

        # Revoke all existing unused codes for this user
        existing = self.session.scalars(
            select(AdminRecoveryCode).where(
                AdminRecoveryCode.created_by == user_id,
                AdminRecoveryCode.revoked_at.is_(None),
            )
        ).all()
        for row in existing:
            row.revoked_at = now

        # Insert new codes
        plaintext_codes: list[str] = []
        for _ in range(count):
            code = _generate_recovery_code()
            plaintext_codes.append(code)
            self.session.add(AdminRecoveryCode(
                code_hash=_hash_code(code),
                created_at=now,
                created_by=actor_user_id,
            ))

        self.session.add(AuditLog(
            actor_user_id=actor_user_id,
            action_type='RECOVERY_CODES_REGENERATED',
            entity_type='USER',
            entity_id=user_id,
            timestamp=now,
            context_json={'count': count, 'revoked': len(existing)},
        ))
        self.session.flush()
        return plaintext_codes

    def verify_recovery_code(self, *, username: str, code: str) -> dict:
        """Verify a recovery code for a username.

        Returns {'valid': True, 'user_id': uuid} on success, or {'valid': False}.
        Raises RecoveryError if rate-limited.
        """
        from app.models.security import AdminRecoveryCode
        now = datetime.now(timezone.utc)
        normalized_user = username.strip().lower()
        normalized_code = code.strip().upper()

        # Rate limit: 5 invalid attempts per username per hour
        # Filter in Python to avoid PostgreSQL JSON .astext query issues
        one_hour_ago = now - timedelta(hours=1)
        attempt_rows = self.session.scalars(
            select(AuditLog).where(
                AuditLog.action_type == 'RECOVERY_CODE_INVALID_ATTEMPT',
                AuditLog.timestamp >= one_hour_ago,
            )
        ).all()
        attempts = sum(
            1
            for a in attempt_rows
            if isinstance(a.context_json, dict)
            and a.context_json.get('username_attempted') == normalized_user
        )
        if attempts >= 5:
            raise RecoveryError('Too many failed attempts. Try again in 1 hour.')

        # Find user
        user = self.session.scalar(select(User).where(func.lower(User.username) == normalized_user))
        if user is None or not user.is_active:
            self._log_invalid_attempt(normalized_user, now, 'user_not_found')
            self.session.commit()
            return {'valid': False}

        # Look up unused, non-revoked codes
        codes = self.session.scalars(
            select(AdminRecoveryCode).where(
                AdminRecoveryCode.created_by == user.id,
                AdminRecoveryCode.used_at.is_(None),
                AdminRecoveryCode.revoked_at.is_(None),
            )
        ).all()

        target_hash = _hash_code(normalized_code)
        for row in codes:
            if row.code_hash == target_hash:
                row.used_at = now
                row.used_by = user.id
                self.session.add(AuditLog(
                    branch_id=user.branch_id,
                    actor_user_id=user.id,
                    action_type='RECOVERY_CODE_USED',
                    entity_type='USER',
                    entity_id=user.id,
                    timestamp=now,
                    context_json={'via': 'forgot_password_flow'},
                ))
                self.session.flush()
                return {'valid': True, 'user_id': user.id}

        self._log_invalid_attempt(normalized_user, now, 'code_mismatch')
        self.session.flush()
        return {'valid': False}

    def _log_invalid_attempt(self, username_lower: str, now: datetime, reason: str) -> None:
        self.session.add(AuditLog(
            action_type='RECOVERY_CODE_INVALID_ATTEMPT',
            entity_type='RECOVERY',
            timestamp=now,
            reason=reason,
            context_json={'username_attempted': username_lower},
        ))