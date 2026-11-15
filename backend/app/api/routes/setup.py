"""First-run setup wizard endpoints.

Chunk 13: join_mode hint.
Chunk 14a: pre-login restore from .ltbak.
Chunk 14b: inspect-backup endpoint.
Chunk 15a: SHA-256 integrity (V2), corruption detection (pg_restore --list),
           rate limit (5 per IP per 10 min, shared bucket with restore).
"""
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.backup.backup_import import (
    detect_format,
    inspect_metadata,
    read_and_hash,
    save_import_file,
    validate_upload,
)
from app.backup.service import BackupError, decrypt_backup, restore_postgres_backup
from app.core import rate_limit
from app.core.config import settings
from app.models.machine_identity import MachineIdentity
from app.models.master import Branch, Role, User
from app.models.security import AuditLog
from app.models.shop_identity import ShopIdentity
from app.schemas.setup import SetupInitializeIn, SetupInitializeOut
from app.security.passwords import hash_password

router = APIRouter(prefix='/setup', tags=['setup'])


# ============================================================================
# Chunk 15a - Rate limit helpers
# Shared bucket across /setup/inspect-backup AND /setup/restore-from-file.
# ============================================================================

def _client_ip(request: Request) -> str:
    # LAN deployment - no trusted proxy - use remote address directly.
    return request.client.host if request.client else "unknown"


def _enforce_rate_limit(request: Request, endpoint: str, db: Session) -> None:
    ip = _client_ip(request)
    decision = rate_limit.check(ip)
    if decision.allowed:
        return
    try:
        db.add(AuditLog(
            action_type="RATE_LIMIT_HIT",
            entity_type="SETUP",
            timestamp=datetime.now(timezone.utc),
            context_json={
                "ip": ip,
                "endpoint": endpoint,
                "attempts": decision.attempts,
                "retry_after_seconds": decision.retry_after_seconds,
            },
        ))
        db.commit()
    except Exception:
        db.rollback()
    minutes = max(1, decision.retry_after_seconds // 60)
    raise HTTPException(
        429,
        "Too many backup attempts. Try again in " + str(minutes) + " minutes.",
        headers={"Retry-After": str(decision.retry_after_seconds)},
    )


def _record_attempt(request: Request) -> None:
    rate_limit.record(_client_ip(request))


def _reset_rate_limit_on_success(request: Request, endpoint: str, db: Session) -> None:
    ip = _client_ip(request)
    rate_limit.reset(ip)
    try:
        db.add(AuditLog(
            action_type="RATE_LIMIT_RESET",
            entity_type="SETUP",
            timestamp=datetime.now(timezone.utc),
            context_json={"ip": ip, "endpoint": endpoint},
        ))
        db.commit()
    except Exception:
        db.rollback()


# ============================================================================
# Chunk 15a - Integrity helpers
# ============================================================================

def _audit_integrity(db: Session, action: str, filename: str | None,
                     sha256: str, error: str | None = None) -> None:
    try:
        db.add(AuditLog(
            action_type=action,
            entity_type="BACKUP",
            timestamp=datetime.now(timezone.utc),
            context_json={
                "filename": filename,
                "sha256_prefix": sha256[:32],
                "error": (error or "")[:200] or None,
            },
        ))
        db.commit()
    except Exception:
        db.rollback()


def _validate_archive(raw_dump: bytes) -> None:
    """Tier 1 corruption check - pg_restore --list on decrypted dump."""
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dump") as tmp:
            tmp.write(raw_dump)
            tmp_path = tmp.name
        result = subprocess.run(
            [settings.pg_restore_bin, "--list", tmp_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()[:300]
            raise HTTPException(
                400,
                "Backup archive is not a valid pg_restore archive: " + (stderr or "unknown error"),
            )
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass


# ============================================================================
# GET /setup/status
# ============================================================================

@router.get('/status')
def setup_status(db: Session = Depends(db_session)):
    """Return whether the shop has been initialized + join_mode hint."""
    try:
        user_count = int(db.scalar(select(func.count()).select_from(User)) or 0)
    except Exception:
        user_count = 0

    try:
        branch_count = int(db.scalar(select(func.count()).select_from(Branch)) or 0)
    except Exception:
        branch_count = 0

    has_admin = False
    if user_count > 0:
        try:
            admin_role = db.scalar(select(Role).where(func.upper(Role.code) == 'ADMIN'))
            if admin_role is not None:
                admin_count = int(
                    db.scalar(
                        select(func.count())
                        .select_from(User)
                        .where(User.role_id == admin_role.id)
                    )
                    or 0
                )
                has_admin = admin_count > 0
        except Exception:
            has_admin = False

    machine = None
    try:
        machine = db.scalar(select(MachineIdentity).limit(1))
    except Exception:
        machine = None

    is_client = machine is not None and machine.machine_role == 'CLIENT'

    if is_client:
        return {
            'is_initialized': True,
            'reason': 'client_ready',
            'user_count': user_count,
            'has_admin': has_admin,
            'join_mode': 'CLIENT_REQUIRES_AUTH',
            'server_url': machine.server_url,
            'can_restore_from_file': False,
            'can_restore_from_cloud': False,
            'available_local_backups': 0,
            'shop_uuid': None,
            'shop_name': None,
        }

    if user_count == 0:
        join_mode = 'SERVER_REQUIRES_SETUP'
        reason = 'no_users'
    elif not has_admin:
        join_mode = 'SERVER_READY'
        reason = 'no_admin_user'
    elif branch_count == 0:
        join_mode = 'SERVER_READY'
        reason = 'no_branch_profile'
    else:
        join_mode = 'SERVER_READY'
        reason = 'ready'

    is_initialized = user_count > 0 and has_admin and branch_count > 0

    try:
        from app.models.backup import BackupPoint
        available_local_backups = int(db.scalar(
            select(func.count()).select_from(BackupPoint).where(
                BackupPoint.state.in_(['VERIFIED', 'IMPORTED'])
            )
        ) or 0)
    except Exception:
        available_local_backups = 0

    shop_uuid_val = None
    shop_name_val = None
    try:
        shop_row = db.scalar(select(ShopIdentity).limit(1))
        if shop_row is not None:
            shop_uuid_val = str(shop_row.shop_uuid)
            shop_name_val = shop_row.shop_name
    except Exception:
        pass

    return {
        'is_initialized': is_initialized,
        'reason': reason,
        'user_count': user_count,
        'has_admin': has_admin,
        'join_mode': join_mode,
        'can_restore_from_file': True,
        'can_restore_from_cloud': False,
        'available_local_backups': available_local_backups,
        'shop_uuid': shop_uuid_val,
        'shop_name': shop_name_val,
    }


# ============================================================================
# POST /setup/inspect-backup
# ============================================================================

@router.post('/inspect-backup')
async def inspect_backup(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(db_session),
):
    """Inspect a .ltbak file (no restore). Returns metadata for UI preview.

    Chunk 15a:
      - Rate limit: 5/10min per IP (shared bucket with restore-from-file)
      - V2: outer SHA-256 verified during decrypt (fail-fast on tamper)
      - Tier 1: pg_restore --list archive validation
      - V1: legacy=True, needs_ack=True
    """
    _enforce_rate_limit(request, '/setup/inspect-backup', db)
    _record_attempt(request)

    filename = file.filename
    sha256 = ""

    try:
        data, sha256 = read_and_hash(file)
        fmt = detect_format(data)
        if fmt == 'SQL':
            raise HTTPException(
                400,
                'Only .ltbak files are supported here. Plain PostgreSQL dumps must be imported via /backup/import-file.',
            )

        try:
            meta_dict, raw_dump = decrypt_backup(data, secret=settings.secret_key)
        except BackupError as exc:
            _audit_integrity(db, "BACKUP_INTEGRITY_FAIL", filename, sha256, str(exc))
            raise HTTPException(400, "Invalid or corrupted backup file: " + str(exc))

        try:
            _validate_archive(raw_dump)
        except HTTPException as exc:
            _audit_integrity(db, "BACKUP_ARCHIVE_FAIL", filename, sha256, str(exc.detail))
            raise

        metadata = inspect_metadata(data, secret=settings.secret_key)
        is_legacy = bool(metadata.get('legacy', False))
        if is_legacy:
            _audit_integrity(db, "BACKUP_LEGACY_NO_HASH", filename, sha256,
                             "V1 file - integrity cannot be verified")
        else:
            _audit_integrity(db, "BACKUP_INTEGRITY_OK", filename, sha256, None)

        _reset_rate_limit_on_success(request, '/setup/inspect-backup', db)

        return {
            'valid': True,
            'format': metadata.get('format'),
            'backup_date': metadata.get('created_at'),
            'sha256': sha256,
            'outer_sha256': metadata.get('outer_sha256'),
            'size_bytes': len(data),
            'shop_uuid': metadata.get('shop_uuid'),
            'shop_name': metadata.get('shop_name'),
            'schema_version': metadata.get('schema_version'),
            'user_count': metadata.get('user_count'),
            'branch_count': metadata.get('branch_count'),
            'source': metadata.get('source'),
            'backup_point_id': metadata.get('backup_point_id'),
            'legacy': is_legacy,
            'needs_ack': is_legacy,
        }
    except HTTPException:
        raise
    except BackupError as exc:
        raise HTTPException(400, "Invalid backup: " + str(exc))
    except Exception as exc:
        raise HTTPException(500, "Inspect failed: " + str(exc))


# ============================================================================
# POST /setup/restore-from-file
# ============================================================================

@router.post('/restore-from-file')
async def restore_from_file(
    request: Request,
    file: UploadFile = File(...),
    confirm_replace: bool = Form(False),
    emergency_key: str = Form(""),
    acknowledge_legacy: bool = Form(False),
    db: Session = Depends(db_session),
):
    """Pre-login restore from a .ltbak file.

    Chunk 15a:
      - Rate limit: 5/10min per IP (shared bucket with inspect-backup)
      - SHA-256 integrity verified via decrypt (V2) before restore attempt
      - Tier 1 pg_restore --list corruption check
      - V1 (legacy) files require acknowledge_legacy=true
      - Automatic safety backup before pg_restore
    """
    _enforce_rate_limit(request, '/setup/restore-from-file', db)
    _record_attempt(request)

    current = setup_status(db)
    if current.get('is_initialized'):
        if not settings.pos_emergency_key or emergency_key != settings.pos_emergency_key:
            raise HTTPException(
                403,
                'Setup already complete. Provide valid emergency_key or use admin restore.',
            )

    if not confirm_replace:
        raise HTTPException(400, 'confirm_replace must be true to proceed')

    filename = file.filename
    sha256 = ""

    try:
        validate_upload(file)
        data, sha256 = read_and_hash(file)
        fmt = detect_format(data)
        if fmt == 'SQL':
            raise HTTPException(
                400,
                'Plain PostgreSQL dumps are not supported here. Use a .ltbak file exported from Lovely Tech POS.',
            )

        try:
            meta_dict, raw_dump = decrypt_backup(data, secret=settings.secret_key)
        except BackupError as exc:
            _audit_integrity(db, "BACKUP_INTEGRITY_FAIL", filename, sha256, str(exc))
            raise HTTPException(400, "Invalid or corrupted backup file: " + str(exc))

        is_legacy = bool(meta_dict.get('_legacy'))
        if is_legacy and not acknowledge_legacy:
            _audit_integrity(db, "BACKUP_LEGACY_NO_HASH", filename, sha256,
                             "Rejected - user did not acknowledge legacy backup")
            raise HTTPException(
                422,
                'This backup was created before integrity checking. Cannot verify SHA-256. Resubmit with acknowledge_legacy=true to proceed.',
            )
        if is_legacy and acknowledge_legacy:
            _audit_integrity(db, "BACKUP_LEGACY_NO_HASH", filename, sha256,
                             "Accepted by user acknowledgement")
        else:
            _audit_integrity(db, "BACKUP_INTEGRITY_OK", filename, sha256, None)

        try:
            _validate_archive(raw_dump)
        except HTTPException as exc:
            _audit_integrity(db, "BACKUP_ARCHIVE_FAIL", filename, sha256, str(exc.detail))
            raise

        metadata = inspect_metadata(data, secret=settings.secret_key)
        dest = save_import_file(data, file.filename or 'backup.ltbak', backup_root=settings.backup_root)
    except BackupError as exc:
        raise HTTPException(400, str(exc))
    except HTTPException:
        raise

    safety = Path(settings.backup_root) / ("pre-login-safety-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + ".ltbak")
    journal = Path(settings.backup_root) / "restore-journal.log"
    journal.parent.mkdir(parents=True, exist_ok=True)

    db.close()

    try:
        restore_postgres_backup(
            pg_dump=settings.pg_dump_bin,
            pg_restore=settings.pg_restore_bin,
            psql=settings.psql_bin,
            database_url=settings.database_url,
            encrypted_backup=dest,
            safety_output=safety,
            secret=settings.secret_key,
        )
    except Exception as exc:
        with journal.open('a', encoding='utf-8') as f:
            f.write(
                datetime.now(timezone.utc).isoformat() + " PRE_LOGIN_RESTORE_FAILED "
                + "file=" + str(file.filename) + " sha=" + sha256[:16] + " error=" + str(exc)[:400] + "\n"
            )
        raise HTTPException(
            500,
            "Restore failed: " + str(exc) + ". Safety backup kept at " + str(safety),
        )

    from app.db.session import get_session_factory
    new_db = get_session_factory()()
    try:
        user_count = int(new_db.scalar(select(func.count()).select_from(User)) or 0)
        branch_count = int(new_db.scalar(select(func.count()).select_from(Branch)) or 0)
        shop = new_db.scalar(select(ShopIdentity).limit(1))

        try:
            new_db.add(AuditLog(
                action_type='PRE_LOGIN_RESTORE_SUCCEEDED',
                entity_type='SYSTEM',
                timestamp=datetime.now(timezone.utc),
                after_json={
                    'filename': file.filename,
                    'sha256': sha256,
                    'size': len(data),
                    'metadata': metadata,
                    'user_count': user_count,
                    'branch_count': branch_count,
                    'shop_uuid': str(shop.shop_uuid) if shop else None,
                    'legacy': is_legacy,
                },
            ))
            new_db.commit()
        except Exception:
            new_db.rollback()

        with journal.open('a', encoding='utf-8') as f:
            f.write(
                datetime.now(timezone.utc).isoformat() + " PRE_LOGIN_RESTORE_SUCCEEDED "
                + "file=" + str(file.filename) + " sha=" + sha256[:16] + " users=" + str(user_count) + "\n"
            )

        rate_limit.reset(_client_ip(request))
        try:
            new_db.add(AuditLog(
                action_type="RATE_LIMIT_RESET",
                entity_type="SETUP",
                timestamp=datetime.now(timezone.utc),
                context_json={"ip": _client_ip(request), "endpoint": "/setup/restore-from-file"},
            ))
            new_db.commit()
        except Exception:
            new_db.rollback()

        return {
            'success': True,
            'shop_uuid': str(shop.shop_uuid) if shop else None,
            'shop_name': shop.shop_name if shop else None,
            'user_count': user_count,
            'branch_count': branch_count,
            'requires_relogin': True,
            'safety_backup': str(safety),
            'legacy': is_legacy,
        }
    finally:
        new_db.close()


# ============================================================================
# POST /setup/initialize (unchanged)
# ============================================================================

@router.post('/initialize', response_model=SetupInitializeOut)
def setup_initialize(
    payload: SetupInitializeIn,
    db: Session = Depends(db_session),
):
    """One-time bootstrap. 409 if any user exists."""
    existing_users = int(db.scalar(select(func.count()).select_from(User)) or 0)
    if existing_users > 0:
        raise HTTPException(
            409,
            'Already initialized - setup cannot be re-run on an existing install',
        )

    try:
        branch = db.scalar(select(Branch).order_by(Branch.created_at).limit(1))
        if branch is None:
            branch = Branch(
                code='MAIN',
                name=payload.shop.name.strip(),
                is_active=True,
                address=(payload.shop.address or '').strip() or None,
                phone=(payload.shop.phone or '').strip() or None,
                email=(payload.shop.email or '').strip() or None,
                invoice_prefix='INV',
            )
            db.add(branch)
            db.flush()
        else:
            branch.name = payload.shop.name.strip()
            branch.address = (payload.shop.address or '').strip() or None
            branch.phone = (payload.shop.phone or '').strip() or None
            branch.email = (payload.shop.email or '').strip() or None

        admin_role = db.scalar(select(Role).where(func.upper(Role.code) == 'ADMIN'))
        if admin_role is None:
            admin_role = Role(code='ADMIN', name='Administrator', is_system=True)
            db.add(admin_role)
            db.flush()

        existing_user = db.scalar(
            select(User).where(User.username == payload.admin.username.strip())
        )
        if existing_user is not None:
            raise HTTPException(400, 'Username already taken')

        admin_user = User(
            username=payload.admin.username.strip(),
            password_hash=hash_password(payload.admin.password),
            display_name=payload.admin.display_name.strip(),
            role_id=admin_role.id,
            branch_id=branch.id,
            is_active=True,
            must_change_password=False,
        )
        db.add(admin_user)
        db.flush()

        db.add(
            AuditLog(
                branch_id=branch.id,
                actor_user_id=admin_user.id,
                action_type='SETUP_INITIALIZED',
                entity_type='BRANCH',
                entity_id=branch.id,
                timestamp=datetime.now(timezone.utc),
                after_json={
                    'shop_name': branch.name,
                    'admin_username': admin_user.username,
                    'admin_display_name': admin_user.display_name,
                },
                source_transaction_id=branch.id,
            )
        )

        from app.services.recovery import RecoveryService
        recovery_codes = RecoveryService(db).generate_recovery_codes(
            user_id=admin_user.id,
            actor_user_id=admin_user.id,
            count=8,
        )

        try:
            shop_identity = db.scalar(select(ShopIdentity).limit(1))
            if shop_identity is not None:
                shop_identity.shop_name = payload.shop.name.strip()
        except Exception:
            pass

        db.commit()

        return SetupInitializeOut(
            success=True,
            branch_id=branch.id,
            admin_user_id=admin_user.id,
            username=admin_user.username,
            recovery_codes=recovery_codes,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, "Setup failed: " + str(e))
