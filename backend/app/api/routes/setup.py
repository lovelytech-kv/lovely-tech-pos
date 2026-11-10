"""First-run setup wizard endpoints.

Public, one-time bootstrap for fresh installs.
Chunk 13: adds `join_mode` to /setup/status to distinguish SERVER vs CLIENT flow.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
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
            'is_initialized': True,           # ← KEY FIX
            'reason': 'client_ready',         # ← KEY FIX
            'user_count': user_count,
            'has_admin': has_admin,
            'join_mode': 'CLIENT_REQUIRES_AUTH',  # keep stable string
            'server_url': machine.server_url,
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

    return {
        'is_initialized': is_initialized,
        'reason': reason,
        'user_count': user_count,
        'has_admin': has_admin,
        'join_mode': join_mode,
    }


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