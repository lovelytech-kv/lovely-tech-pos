"""First-run setup wizard endpoints.

Public, one-time bootstrap for fresh installs:
- GET  /api/v1/setup/status       — tells frontend if wizard is needed
- POST /api/v1/setup/initialize   — creates main branch + admin role + admin user

Once any user exists, POST /setup/initialize always returns 409.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.models.master import Branch, Role, User
from app.models.security import AuditLog
from app.schemas.setup import (
    SetupInitializeIn,
    SetupInitializeOut,
    SetupStatusOut,
)
from app.security.passwords import hash_password

router = APIRouter(prefix='/setup', tags=['setup'])


@router.get('/status', response_model=SetupStatusOut)
def setup_status(db: Session = Depends(db_session)):
    """Return whether the shop has been initialized.

    Tolerates any DB state. Never raises for missing tables — if the DB
    is truly empty (post-migration), counts return 0.
    """
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
            admin_role = db.scalar(
                select(Role).where(func.upper(Role.code) == 'ADMIN')
            )
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

    if user_count == 0:
        reason = 'no_users'
    elif not has_admin:
        reason = 'no_admin_user'
    elif branch_count == 0:
        reason = 'no_branch_profile'
    else:
        return SetupStatusOut(
            is_initialized=True,
            reason='ready',
            user_count=user_count,
            has_admin=has_admin,
        )

    return SetupStatusOut(
        is_initialized=False,
        reason=reason,
        user_count=user_count,
        has_admin=has_admin,
    )


@router.post('/initialize', response_model=SetupInitializeOut)
def setup_initialize(
    payload: SetupInitializeIn,
    db: Session = Depends(db_session),
):
    """One-time bootstrap.

    Idempotent-safety: if ANY user exists, return 409 immediately.
    All work happens in a single DB transaction (rollback on any failure).
    """
    existing_users = int(db.scalar(select(func.count()).select_from(User)) or 0)
    if existing_users > 0:
        raise HTTPException(
            409,
            'Already initialized — setup cannot be re-run on an existing install',
        )

    try:
        # --- 1. MAIN branch (create or update) ---
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
            # No users exist → safe to update this orphan branch
            branch.name = payload.shop.name.strip()
            branch.address = (payload.shop.address or '').strip() or None
            branch.phone = (payload.shop.phone or '').strip() or None
            branch.email = (payload.shop.email or '').strip() or None

        # --- 2. ADMIN role (create if missing) ---
        admin_role = db.scalar(select(Role).where(func.upper(Role.code) == 'ADMIN'))
        if admin_role is None:
            admin_role = Role(code='ADMIN', name='Administrator', is_system=True)
            db.add(admin_role)
            db.flush()

        # --- 3. Username uniqueness (defensive — no users exist per check above) ---
        existing_user = db.scalar(
            select(User).where(User.username == payload.admin.username.strip())
        )
        if existing_user is not None:
            raise HTTPException(400, 'Username already taken')

        # --- 4. Admin user ---
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

        # --- 5. Audit log ---
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

        db.commit()

        return SetupInitializeOut(
            success=True,
            branch_id=branch.id,
            admin_user_id=admin_user.id,
            username=admin_user.username,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f'Setup failed: {e}')