"""First-run setup wizard endpoints.

Public, one-time bootstrap for fresh installs.
Chunk 13: adds `join_mode` to /setup/status to distinguish SERVER vs CLIENT flow.
Chunk 14a: pre-login restore from .ltbak file.
"""
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.models.master import Branch, Role, User
from app.models.machine_identity import MachineIdentity
from app.models.security import AuditLog
from app.models.shop_identity import ShopIdentity
from app.schemas.setup import SetupInitializeIn, SetupInitializeOut
from app.security.passwords import hash_password

router = APIRouter(prefix='/setup', tags=['setup'])


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

    # ─── Chunk 13: check machine_identity FIRST ───
    machine = None
    try:
        machine = db.scalar(select(MachineIdentity).limit(1))
    except Exception:
        machine = None

    is_client = machine is not None and machine.machine_role == 'CLIENT'

    if is_client:
        # CLIENT mode — setup complete via join. No local admin/branch needed.
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
        }

    # ─── SERVER mode logic ───
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

    # Chunk 14a — backup restore hints
    try:
        from app.models.backup import BackupPoint
        available_local_backups = int(db.scalar(
            select(func.count()).select_from(BackupPoint).where(
                BackupPoint.state.in_(['VERIFIED', 'IMPORTED'])
            )
        ) or 0)
    except Exception:
        available_local_backups = 0

    return {
        'is_initialized': is_initialized,
        'reason': reason,
        'user_count': user_count,
        'has_admin': has_admin,
        'join_mode': join_mode,
        'can_restore_from_file': True,
        'can_restore_from_cloud': False,
        'available_local_backups': available_local_backups,
    }

@router.post('/inspect-backup')
async def inspect_backup(
    file: UploadFile = File(...),
    db: Session = Depends(db_session),
):
    """Inspect a .ltbak file (no restore). Returns metadata for UI preview.

    Public — used during pre-login restore flow. Old backups (pre-Chunk 14b)
    may lack shop_uuid / shop_name / user_count in metadata.
    """
    from app.backup.service import BackupError
    from app.backup.backup_import import read_and_hash, inspect_metadata, detect_format
    from app.core.config import settings

    try:
        data, sha256 = read_and_hash(file)
        fmt = detect_format(data)
        if fmt != 'LTPOS-BACKUP-V1':
            if data.startswith(b'PGDMP'):
                raise HTTPException(400, 'Only .ltbak files are supported here. Plain PostgreSQL dumps must be imported via /backup/import-file.')
            raise HTTPException(400, 'Invalid or corrupted backup file. Select a valid .ltbak exported from Lovely Tech POS.')
        metadata = inspect_metadata(data, secret=settings.secret_key)
    except BackupError as exc:
        raise HTTPException(400, f'Invalid backup: {exc}')
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f'Inspect failed: {exc}')

    # Best-effort audit log (fresh install may have no branch/user)
    try:
        db.add(AuditLog(
            action_type='BACKUP_INSPECTED',
            entity_type='SYSTEM',
            timestamp=datetime.now(timezone.utc),
            after_json={
                'filename': file.filename,
                'sha256': sha256,
                'size': len(data),
                'shop_uuid': metadata.get('shop_uuid'),
            },
        ))
        db.commit()
    except Exception:
        db.rollback()

    return {
        'valid': True,
        'format': metadata.get('format'),
        'backup_date': metadata.get('created_at'),
        'sha256': sha256,
        'size_bytes': len(data),
        'shop_uuid': metadata.get('shop_uuid'),
        'shop_name': metadata.get('shop_name'),
        'schema_version': metadata.get('schema_version'),
        'user_count': metadata.get('user_count'),
        'branch_count': metadata.get('branch_count'),
        'source': metadata.get('source'),
        'backup_point_id': metadata.get('backup_point_id'),
    }


@router.post('/restore-from-file')
async def restore_from_file(
    file: UploadFile = File(...),
    confirm_replace: bool = Form(False),
    emergency_key: str = Form(""),
    db: Session = Depends(db_session),
):
    """Pre-login restore from a .ltbak file.

    Only allowed when setup is NOT initialized, OR with valid POS_EMERGENCY_KEY
    (bypass). Requires confirm_replace=true.
    """
    from app.backup.service import BackupError, restore_postgres_backup
    from app.backup.backup_import import (
        validate_upload, read_and_hash, inspect_metadata, save_import_file, detect_format,
    )
    from app.core.config import settings
    from app.db.session import get_session_factory

    # ── 1. Authorization ──
    current = setup_status(db)
    if current.get('is_initialized'):
        if not settings.pos_emergency_key or emergency_key != settings.pos_emergency_key:
            raise HTTPException(
                403,
                'Setup already complete. Provide valid emergency_key or use admin restore.',
            )

    if not confirm_replace:
        raise HTTPException(400, 'confirm_replace must be true to proceed')

    # ── 2. Validate + inspect file ──
    try:
        validate_upload(file)
        data, sha256 = read_and_hash(file)
        fmt = detect_format(data)
        if fmt != 'LTPOS-BACKUP-V1':
            if data.startswith(b'PGDMP'):
                raise HTTPException(400, 'Plain PostgreSQL dumps are not supported here. Use a .ltbak file exported from Lovely Tech POS.')
            raise HTTPException(400, 'Invalid or corrupted backup file. Select a valid .ltbak exported from Lovely Tech POS.')
        metadata = inspect_metadata(data, secret=settings.secret_key)
        dest = save_import_file(data, file.filename or 'backup.ltbak', backup_root=settings.backup_root)
    except BackupError as exc:
        raise HTTPException(400, str(exc))

    safety = Path(settings.backup_root) / f"pre-login-safety-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.ltbak"
    journal = Path(settings.backup_root) / "restore-journal.log"
    journal.parent.mkdir(parents=True, exist_ok=True)

    # ── 3. Close session before in-place restore ──
    db.close()

    # ── 4. Run restore (in-place, safety backup taken inside) ──
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
                f"{datetime.now(timezone.utc).isoformat()} PRE_LOGIN_RESTORE_FAILED "
                f"file={file.filename} sha={sha256[:16]} error={str(exc)[:400]}\n"
            )
        raise HTTPException(
            500,
            f'Restore failed: {exc}. Safety backup kept at {safety}',
        )

    # ── 5. Verify + audit (fresh session on restored DB) ──
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
                },
            ))
            new_db.commit()
        except Exception:
            new_db.rollback()

        with journal.open('a', encoding='utf-8') as f:
            f.write(
                f"{datetime.now(timezone.utc).isoformat()} PRE_LOGIN_RESTORE_SUCCEEDED "
                f"file={file.filename} sha={sha256[:16]} users={user_count}\n"
            )

        return {
            'success': True,
            'shop_uuid': str(shop.shop_uuid) if shop else None,
            'shop_name': shop.shop_name if shop else None,
            'user_count': user_count,
            'branch_count': branch_count,
            'requires_relogin': True,
            'safety_backup': str(safety),
        }
    finally:
        new_db.close()


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
            'Already initialized — setup cannot be re-run on an existing install',
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
        raise HTTPException(500, f'Setup failed: {e}')