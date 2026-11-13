from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.models.master import Branch, User
from app.models.security import AuditLog
from app.models.shop_identity import ShopIdentity
from app.schemas.api import BranchProfileOut, BranchProfileUpdateIn, BranchPublicOut

router = APIRouter(prefix='/branch', tags=['branch'])

MAX_LOGO_BASE64 = 700 * 1024
ALLOWED_MIMES = {'image/png', 'image/jpeg', 'image/svg+xml'}


def _to_public(branch: Branch) -> BranchPublicOut:
    return BranchPublicOut(
        name=branch.name,
        logo_base64=branch.logo_base64,
        logo_mime=branch.logo_mime,
        logo_base64_light=branch.logo_base64_light or branch.logo_base64,
        logo_mime_light=branch.logo_mime_light or branch.logo_mime,
        logo_base64_dark=branch.logo_base64_dark,
        logo_mime_dark=branch.logo_mime_dark,
    )


def _to_profile(branch: Branch) -> BranchProfileOut:
    return BranchProfileOut(
        branch_id=branch.id,
        code=branch.code,
        name=branch.name,
        address=branch.address,
        phone=branch.phone,
        email=branch.email,
        logo_base64=branch.logo_base64,
        logo_mime=branch.logo_mime,
        logo_base64_light=branch.logo_base64_light or branch.logo_base64,
        logo_mime_light=branch.logo_mime_light or branch.logo_mime,
        logo_base64_dark=branch.logo_base64_dark,
        logo_mime_dark=branch.logo_mime_dark,
        invoice_prefix=branch.invoice_prefix or 'INV',
    )


def _validate_logo(base64_val: str | None, mime_val: str | None, label: str) -> None:
    if not base64_val:
        return
    if len(base64_val) > MAX_LOGO_BASE64:
        raise HTTPException(400, f'{label} logo is too large (max 500KB after encoding)')
    if mime_val not in ALLOWED_MIMES:
        raise HTTPException(400, f'{label} logo must be one of: {", ".join(sorted(ALLOWED_MIMES))}')


@router.get('/public', response_model=BranchPublicOut)
def get_public_branch(db: Session = Depends(db_session)):
    branch = db.scalar(
        select(Branch)
        .where(Branch.is_active.is_(True))
        .order_by(Branch.created_at)
    )
    if branch is None:
        raise HTTPException(404, 'No active branch configured')
    return _to_public(branch)


@router.get('/profile', response_model=BranchProfileOut)
def get_branch_profile(
    user: User = Depends(require_permission('SALE_CREATE')),
    db: Session = Depends(db_session),
):
    branch = db.get(Branch, user.branch_id)
    if branch is None:
        raise HTTPException(404, 'Branch not found')
    return _to_profile(branch)


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

    # Light logo — prefer explicit light field, else legacy field, else no change
    light_b64_sent = payload.logo_base64_light is not None
    light_mime_sent = payload.logo_mime_light
    legacy_b64_sent = payload.logo_base64 is not None
    legacy_mime_sent = payload.logo_mime

    if light_b64_sent:
        _validate_logo(payload.logo_base64_light, light_mime_sent, 'Light-mode')
    elif legacy_b64_sent:
        _validate_logo(payload.logo_base64, legacy_mime_sent, 'Light-mode')

    # Dark logo
    if payload.logo_base64_dark is not None:
        _validate_logo(payload.logo_base64_dark, payload.logo_mime_dark, 'Dark-mode')

    before = {
        'name': branch.name,
        'address': branch.address,
        'phone': branch.phone,
        'email': branch.email,
        'invoice_prefix': branch.invoice_prefix,
        'logo_light_present': bool(branch.logo_base64_light or branch.logo_base64),
        'logo_dark_present': bool(branch.logo_base64_dark),
    }

    branch.name = name
    branch.address = (payload.address or '').strip() or None
    branch.phone = (payload.phone or '').strip() or None
    branch.email = (payload.email or '').strip() or None
    branch.invoice_prefix = (payload.invoice_prefix or 'INV').strip() or 'INV'

    # Chunk 14c polish — write-layer sync: keep shop_identity.shop_name in lockstep
    # so /health, /setup/status, mDNS TXT, and backup metadata see the same name.
    # Same transaction; rolls back together with the branch update if commit fails.
    shop_identity = db.scalar(select(ShopIdentity).limit(1).with_for_update())
    if shop_identity is not None and shop_identity.shop_name != name:
        shop_identity.shop_name = name
    # Update light logo
    if light_b64_sent:
        if payload.logo_base64_light == '':
            branch.logo_base64_light = None
            branch.logo_mime_light = None
        else:
            branch.logo_base64_light = payload.logo_base64_light
            branch.logo_mime_light = light_mime_sent or None
    elif legacy_b64_sent:
        if payload.logo_base64 == '':
            branch.logo_base64_light = None
            branch.logo_mime_light = None
        else:
            branch.logo_base64_light = payload.logo_base64
            branch.logo_mime_light = legacy_mime_sent or None

    # Update dark logo
    if payload.logo_base64_dark is not None:
        if payload.logo_base64_dark == '':
            branch.logo_base64_dark = None
            branch.logo_mime_dark = None
        else:
            branch.logo_base64_dark = payload.logo_base64_dark
            branch.logo_mime_dark = payload.logo_mime_dark or None

    after = {
        'name': branch.name,
        'address': branch.address,
        'phone': branch.phone,
        'email': branch.email,
        'invoice_prefix': branch.invoice_prefix,
        'logo_light_present': bool(branch.logo_base64_light or branch.logo_base64),
        'logo_dark_present': bool(branch.logo_base64_dark),
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
    return _to_profile(branch)