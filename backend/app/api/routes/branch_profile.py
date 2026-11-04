from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.models.master import Branch, User
from app.models.security import AuditLog
from app.schemas.api import BranchProfileOut, BranchProfileUpdateIn, BranchPublicOut

router = APIRouter(prefix='/branch', tags=['branch'])

# 500KB raw image → ~666KB base64 → cap base64 string at 700KB (safe headroom)
MAX_LOGO_BASE64 = 700 * 1024
ALLOWED_MIMES = {'image/png', 'image/jpeg', 'image/svg+xml'}


@router.get('/public', response_model=BranchPublicOut)
def get_public_branch(db: Session = Depends(db_session)):
    """Public branding used on the login screen (no auth required)."""
    branch = db.scalar(
        select(Branch)
        .where(Branch.is_active.is_(True))
        .order_by(Branch.created_at)
    )
    if branch is None:
        raise HTTPException(404, 'No active branch configured')
    return BranchPublicOut(
        name=branch.name,
        logo_base64=branch.logo_base64,
        logo_mime=branch.logo_mime,
    )


@router.get('/profile', response_model=BranchProfileOut)
def get_branch_profile(
    user: User = Depends(require_permission('SALE_CREATE')),
    db: Session = Depends(db_session),
):
    branch = db.get(Branch, user.branch_id)
    if branch is None:
        raise HTTPException(404, 'Branch not found')
    return BranchProfileOut(
        branch_id=branch.id,
        code=branch.code,
        name=branch.name,
        address=branch.address,
        phone=branch.phone,
        email=branch.email,
        logo_base64=branch.logo_base64,
        logo_mime=branch.logo_mime,
        invoice_prefix=branch.invoice_prefix or 'INV',
    )


@router.put('/profile', response_model=BranchProfileOut)
def update_branch_profile(
    payload: BranchProfileUpdateIn,
    user: User = Depends(require_permission('ADMIN_PANEL')),
    db: Session = Depends(db_session),
):
    branch = db.scalar(
        select(Branch).where(Branch.id == user.branch_id).with_for_update()
    )
    if branch is None:
        raise HTTPException(404, 'Branch not found')

    name = (payload.name or '').strip()
    if not name:
        raise HTTPException(400, 'Shop name is required')

    if payload.logo_base64:
        if len(payload.logo_base64) > MAX_LOGO_BASE64:
            raise HTTPException(400, 'Logo is too large (max 500KB after encoding)')
        if payload.logo_mime not in ALLOWED_MIMES:
            raise HTTPException(
                400,
                f'Logo must be one of: {", ".join(sorted(ALLOWED_MIMES))}',
            )

    before = {
        'name': branch.name,
        'address': branch.address,
        'phone': branch.phone,
        'email': branch.email,
        'invoice_prefix': branch.invoice_prefix,
        'logo_present': bool(branch.logo_base64),
    }

    branch.name = name
    branch.address = (payload.address or '').strip() or None
    branch.phone = (payload.phone or '').strip() or None
    branch.email = (payload.email or '').strip() or None
    branch.invoice_prefix = (payload.invoice_prefix or 'INV').strip() or 'INV'

    # Logo: only change if the client sent the field (undefined → keep current)
    # An explicit empty string ('') means "remove logo".
    if payload.logo_base64 is not None:
        if payload.logo_base64 == '':
            branch.logo_base64 = None
            branch.logo_mime = None
        else:
            branch.logo_base64 = payload.logo_base64
            branch.logo_mime = payload.logo_mime or None

    after = {
        'name': branch.name,
        'address': branch.address,
        'phone': branch.phone,
        'email': branch.email,
        'invoice_prefix': branch.invoice_prefix,
        'logo_present': bool(branch.logo_base64),
    }

    db.add(
        AuditLog(
            branch_id=user.branch_id,
            actor_user_id=user.id,
            action_type='BRANCH_PROFILE_UPDATE',
            entity_type='BRANCH',
            entity_id=branch.id,
            timestamp=datetime.now(timezone.utc),
            before_json=before,
            after_json=after,
            source_transaction_id=branch.id,
        )
    )
    db.commit()

    return BranchProfileOut(
        branch_id=branch.id,
        code=branch.code,
        name=branch.name,
        address=branch.address,
        phone=branch.phone,
        email=branch.email,
        logo_base64=branch.logo_base64,
        logo_mime=branch.logo_mime,
        invoice_prefix=branch.invoice_prefix or 'INV',
    )