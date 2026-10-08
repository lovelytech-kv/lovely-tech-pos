from __future__ import annotations
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.inventory import StockAdjustment, DamageLossRecord, StockMovement, PurchaseLot, FifoAllocation
from app.models.security import AuditLog
from app.fifo.engine import FifoEngine

class StockControlError(ValueError): pass

class StockControlService:
    def __init__(self, session: Session):
        self.session=session; self.fifo=FifoEngine(session)
    def _stock(self, branch_id, item_id):
        return Decimal(self.session.scalar(select(func.coalesce(func.sum(StockMovement.quantity_delta),0)).where(StockMovement.branch_id==branch_id,StockMovement.item_id==item_id)) or 0)
    def adjust(self, *, branch_id, item_id, quantity_delta, reason, user_id, approved_by=None):
        quantity_delta=Decimal(quantity_delta)
        if quantity_delta==0: raise StockControlError('Quantity adjustment cannot be zero')
        if not reason.strip(): raise StockControlError('Adjustment reason is required')
        row=StockAdjustment(branch_id=branch_id,item_id=item_id,quantity_delta=quantity_delta,reason=reason,approved_by=approved_by or user_id)
        self.session.add(row); self.session.flush()
        now=datetime.now(timezone.utc)
        if quantity_delta > 0:
            movement=StockMovement(branch_id=branch_id,item_id=item_id,source_type='STOCK_ADJUSTMENT',source_id=row.id,quantity_delta=quantity_delta,occurred_at=now,reason=reason)
            self.session.add(movement); self.session.flush()
            latest=self.session.scalar(select(PurchaseLot).where(PurchaseLot.branch_id==branch_id,PurchaseLot.item_id==item_id,PurchaseLot.lot_date<=now.date()).order_by(PurchaseLot.lot_date.desc(),PurchaseLot.created_at.desc(),PurchaseLot.id.desc()).with_for_update())
            if latest is None:
                raise StockControlError('A positive stock correction requires an existing purchase-lot cost reference')
            self.session.add(FifoAllocation(stock_movement_id=movement.id,purchase_lot_id=None,allocated_quantity=quantity_delta,allocated_unit_cost=latest.unit_cost,allocation_status='ADJUSTMENT_POOL',created_at=now))
        else:
            self.fifo.consume(branch_id=branch_id,item_id=item_id,quantity=-quantity_delta,source_type='STOCK_ADJUSTMENT',source_id=row.id,occurred_at=now,reason=reason)
        self.session.add(AuditLog(branch_id=branch_id,actor_user_id=user_id,action_type='STOCK_ADJUSTMENT',entity_type='STOCK_ADJUSTMENT',entity_id=row.id,timestamp=now,reason=reason,after_json={'quantity_delta':str(quantity_delta)},source_transaction_id=row.id))
        self.session.flush(); return row
    def damage_loss(self, *, branch_id,item_id,quantity,reason,user_id,source_type=None,source_id=None):
        quantity=Decimal(quantity)
        if quantity<=0: raise StockControlError('Damage/loss quantity must be positive')
        if not reason.strip(): raise StockControlError('Damage/loss reason is required')
        row=DamageLossRecord(branch_id=branch_id,item_id=item_id,quantity=quantity,reason=reason,source_type=source_type,source_id=source_id,approved_by=user_id)
        self.session.add(row); self.session.flush()
        result=self.fifo.consume(branch_id=branch_id,item_id=item_id,quantity=quantity,source_type='DAMAGE_LOSS',source_id=row.id,occurred_at=datetime.now(timezone.utc),reason=reason)
        self.session.add(AuditLog(branch_id=branch_id,actor_user_id=user_id,action_type='DAMAGE_LOSS',entity_type='DAMAGE_LOSS',entity_id=row.id,timestamp=datetime.now(timezone.utc),reason=reason,after_json={'quantity':str(quantity),'fifo_cost':str(result.total_cost)}))
        self.session.flush(); return row,result
