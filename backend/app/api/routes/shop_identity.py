"""Shop identity endpoints (Chunk 12a)."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.models.master import Branch, User
from app.models.security import AuditLog
from app.models.shop_identity import ShopIdentity
from app.schemas.api import ShopIdentityOut, ShopNameUpdateIn

router = APIRouter(prefix='/shop', tags=['shop'])


@router.get('/identity', response_model=ShopIdentityOut)
def get_shop_identity(db: Session = Depends(db_session)):
    """Public — used by frontend + external systems to identify this shop."""
    shop = db.scalar(select(ShopIdentity).limit(1))
    if shop is None:
        raise HTTPException(500, 'Shop identity not initialized (migration 0040 not applied)')
    return ShopIdentityOut(
        shop_uuid=shop.shop_uuid,
        shop_name=shop.shop_name,
        schema_version=shop.schema_version,
        created_at=shop.created_at,
    )


@router.put('/identity/shop-name', response_model=ShopIdentityOut)
def update_shop_name(
    payload: ShopNameUpdateIn,
    user: User = Depends(require_permission('ADMIN_PANEL')),
    db: Session = Depends(db_session),
):
    """Admin — update shop name in shop_identity AND branches.name (kept in sync)."""
    shop = db.scalar(select(ShopIdentity).limit(1).with_for_update())
    if shop is None:
        raise HTTPException(500, 'Shop identity not initialized')

    new_name = (payload.shop_name or '').strip()
    if not new_name:
        raise HTTPException(400, 'Shop name is required')

    branch = db.scalar(select(Branch).order_by(Branch.created_at).limit(1).with_for_update())

    before = {
        'shop_name': shop.shop_name,
        'branch_name': branch.name if branch else None,
    }

    shop.shop_name = new_name
    if branch is not None:
        branch.name = new_name

    db.add(AuditLog(
        branch_id=user.branch_id,
        actor_user_id=user.id,
        action_type='SHOP_NAME_UPDATED',
        entity_type='SHOP',
        entity_id=shop.id,
        timestamp=datetime.now(timezone.utc),
        before_json=before,
        after_json={
            'shop_name': shop.shop_name,
            'branch_name': branch.name if branch else None,
        },
        source_transaction_id=shop.id,
    ))
    db.commit()

    return ShopIdentityOut(
        shop_uuid=shop.shop_uuid,
        shop_name=shop.shop_name,
        schema_version=shop.schema_version,
        created_at=shop.created_at,
    )