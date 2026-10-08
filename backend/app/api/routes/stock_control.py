from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import db_session, require_permission
from app.models.master import User
from app.models.security import IdempotencyKey
from app.schemas.api import StockAdjustIn, DamageLossIn
from app.services.stock_control import StockControlService, StockControlError
from app.security.reauth import require_admin_reauth
from datetime import datetime, timezone
import hashlib, json, uuid

router=APIRouter(prefix='/stock-control',tags=['stock-control'])

def _adjust_request_hash(p: StockAdjustIn) -> str:
    raw = json.dumps({
        "item_id": str(p.item_id),
        "quantity_delta": str(p.quantity_delta),
        "reason": p.reason,
    }, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()

def _damage_request_hash(p: DamageLossIn) -> str:
    raw = json.dumps({
        "item_id": str(p.item_id),
        "quantity": str(p.quantity),
        "reason": p.reason,
    }, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()

def _get_replay(db: Session, *, key: str | None, request_hash: str) -> dict | None:
    if not key:
        return None
    existing = db.scalar(select(IdempotencyKey).where(IdempotencyKey.key == key).with_for_update())
    if existing is None:
        return None
    if existing.request_hash != request_hash:
        raise HTTPException(409, "Idempotency key was already used for a different request")
    if not existing.completed_at or not existing.response_json:
        raise HTTPException(409, "The same request is currently being completed; retry after transaction finishes")
    return existing.response_json

def _reserve(db: Session, *, key: str | None, user_id: uuid.UUID, request_hash: str, response: dict) -> None:
    if not key:
        return
    row = IdempotencyKey(key=key, user_id=user_id, request_hash=request_hash, created_at=datetime.now(timezone.utc), response_json=response, completed_at=datetime.now(timezone.utc))
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = db.scalar(select(IdempotencyKey).where(IdempotencyKey.key == key).with_for_update())
        if existing is None or existing.request_hash != request_hash:
            raise HTTPException(409, "Idempotency key was already used for a different request")
        raise HTTPException(409, "Idempotency request has already completed")

@router.post('/adjust',dependencies=[Depends(require_permission('STOCK_ADJUST'))])
def adjust(p:StockAdjustIn,admin_password:str|None=None,user:User=Depends(require_permission('STOCK_ADJUST')),db:Session=Depends(db_session)):
    require_admin_reauth(user=user,password=admin_password,db=db,action='stock adjustment')
    request_hash=_adjust_request_hash(p)
    replay=_get_replay(db, key=p.idempotency_key, request_hash=request_hash)
    if replay is not None:
        return replay
    try:
        r=StockControlService(db).adjust(branch_id=user.branch_id,item_id=p.item_id,quantity_delta=p.quantity_delta,reason=p.reason,user_id=user.id)
        response={'adjustment_id':str(r.id)}
        _reserve(db, key=p.idempotency_key, user_id=user.id, request_hash=request_hash, response=response)
        db.commit()
        return response
    except (StockControlError, ValueError) as e:
        db.rollback(); raise HTTPException(400, str(e))
    except HTTPException:
        db.rollback(); raise

@router.post('/damage-loss',dependencies=[Depends(require_permission('STOCK_ADJUST'))])
def damage(p:DamageLossIn,admin_password:str|None=None,user:User=Depends(require_permission('STOCK_ADJUST')),db:Session=Depends(db_session)):
    require_admin_reauth(user=user,password=admin_password,db=db,action='damage/loss approval')
    request_hash=_damage_request_hash(p)
    replay=_get_replay(db, key=p.idempotency_key, request_hash=request_hash)
    if replay is not None:
        return replay
    try:
        r=StockControlService(db).damage_loss(branch_id=user.branch_id,item_id=p.item_id,quantity=p.quantity,reason=p.reason,user_id=user.id)
        response={'damage_loss_id':str(r[0].id),'fifo_cost':str(r[1].total_cost)}
        _reserve(db, key=p.idempotency_key, user_id=user.id, request_hash=request_hash, response=response)
        db.commit()
        return response
    except (StockControlError, ValueError) as e:
        db.rollback(); raise HTTPException(400, str(e))
    except HTTPException:
        db.rollback(); raise