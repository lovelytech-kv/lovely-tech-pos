"""Admin-only back-fill endpoints for records that must carry a PAST date (old spreadsheet history).

Everything else (purchases, sales, expenses, other income) already accepts past dates through the normal APIs;
repairs and damage/loss always stamped "now", so these two exist only for the one-time history import.
"""
import hashlib
import json
from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.api.routes.stock_control import _get_replay, _reserve
from app.models.master import User
from app.security.reauth import require_admin_reauth
from app.services.repairs import RepairService, RepairValidationError
from app.services.stock_control import StockControlError, StockControlService

router = APIRouter(prefix="/admin/history", tags=["history-import"])


def admin_user(user: User = Depends(require_permission("ADMIN_PANEL"))) -> User:
    return user


class HistoricalRepairIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    done_on: date
    device_brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=150)
    description: str | None = None
    final_amount: Decimal = Field(ge=0)
    parts_cost: Decimal = Field(default=Decimal("0"), ge=0)
    history_ref: str = Field(min_length=6, max_length=100)
    cost_item_id: UUID | None = None
    notes: str | None = None


class HistoricalDamageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: UUID
    quantity: Decimal = Field(gt=0)
    occurred_on: date
    reason: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=8, max_length=200)


@router.post("/repairs")
def import_repair(p: HistoricalRepairIn, admin_password: str | None = None, user: User = Depends(admin_user), db: Session = Depends(db_session)):
    require_admin_reauth(user=user, password=admin_password, db=db, action="historical repair import")
    try:
        repair, replayed = RepairService(db).import_historical(
            branch_id=user.branch_id, actor_user_id=user.id, done_on=p.done_on, device_brand=p.device_brand, model=p.model,
            description=p.description, final_amount=p.final_amount, parts_cost=p.parts_cost, history_ref=p.history_ref,
            cost_item_id=p.cost_item_id, notes=p.notes)
        db.commit()
        return {"repair_id": str(repair.id), "repair_no": repair.repair_no, "replayed": replayed}
    except RepairValidationError as exc:
        db.rollback()
        raise HTTPException(400, str(exc))


@router.post("/damage-loss")
def import_damage_loss(p: HistoricalDamageIn, admin_password: str | None = None, user: User = Depends(admin_user), db: Session = Depends(db_session)):
    require_admin_reauth(user=user, password=admin_password, db=db, action="historical damage/loss import")
    request_hash = hashlib.sha256(json.dumps({"i": str(p.item_id), "q": str(p.quantity), "d": str(p.occurred_on), "r": p.reason}, sort_keys=True).encode()).hexdigest()
    replay = _get_replay(db, key=p.idempotency_key, request_hash=request_hash)
    if replay is not None:
        return replay
    try:
        when = datetime.combine(p.occurred_on, time(12, 0), tzinfo=timezone.utc)
        row, result = StockControlService(db).damage_loss(branch_id=user.branch_id, item_id=p.item_id, quantity=p.quantity, reason=p.reason,
                                                          user_id=user.id, occurred_at=when)
        response = {"damage_loss_id": str(row.id), "fifo_cost": str(result.total_cost)}
        _reserve(db, key=p.idempotency_key, user_id=user.id, request_hash=request_hash, response=response)
        db.commit()
        return response
    except (StockControlError, ValueError) as exc:
        db.rollback()
        raise HTTPException(400, str(exc))
