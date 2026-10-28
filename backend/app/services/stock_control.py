from __future__ import annotations
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.inventory import StockAdjustment, DamageLossRecord, StockMovement, PurchaseLot, FifoAllocation, SerializedUnit
from app.models.master import Item
from app.models.security import AuditLog
from app.fifo.engine import FifoEngine

class StockControlError(ValueError): pass

class StockControlService:
    def __init__(self, session: Session):
        self.session=session; self.fifo=FifoEngine(session)
    def _stock(self, branch_id, item_id):
        return Decimal(self.session.scalar(select(func.coalesce(func.sum(StockMovement.quantity_delta),0)).where(StockMovement.branch_id==branch_id,StockMovement.item_id==item_id)) or 0)
    def _serialized_out(self, *, branch_id, item_id, quantity, unit_ids, status):
        """IMEI-tracked items: stock can only go down by naming the exact phones, which leave IN_STOCK (else a phone could
        still be sold after the stock count said it was gone)."""
        item=self.session.get(Item,item_id)
        if item is None or not self._is_serialized(item): return
        ids=list(dict.fromkeys(unit_ids or []))
        if quantity!=len(ids): raise StockControlError(f'{item.item_code} is IMEI-tracked: select exactly {int(quantity)} phone(s) (IMEI) - {len(ids)} selected')
        units=self.session.scalars(select(SerializedUnit).where(SerializedUnit.id.in_(ids),SerializedUnit.branch_id==branch_id,SerializedUnit.item_id==item_id).with_for_update()).all()
        if len(units)!=len(ids): raise StockControlError('Selected IMEI does not belong to this item')
        bad=[u.serial_number for u in units if u.status!='IN_STOCK']
        if bad: raise StockControlError('Only IN_STOCK phones can be written off; not available: '+', '.join(bad))
        for u in units: u.status=status
    def _is_serialized(self, item):
        from app.models.master import ItemType
        t=self.session.get(ItemType,item.item_type_id)
        return bool(t and t.is_serialized)
    def adjust(self, *, branch_id, item_id, quantity_delta, reason, user_id, approved_by=None, serialized_unit_ids=None):
        quantity_delta=Decimal(quantity_delta)
        if quantity_delta==0: raise StockControlError('Quantity adjustment cannot be zero')
        if not reason.strip(): raise StockControlError('Adjustment reason is required')
        item=self.session.get(Item,item_id)
        if quantity_delta>0 and item is not None and self._is_serialized(item):
            raise StockControlError('IMEI-tracked phones cannot be added by a stock adjustment: enter them in Purchases with their IMEI')
        if quantity_delta<0: self._serialized_out(branch_id=branch_id,item_id=item_id,quantity=-quantity_delta,unit_ids=serialized_unit_ids,status='WRITTEN_OFF')
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
    def damage_loss(self, *, branch_id,item_id,quantity,reason,user_id,source_type=None,source_id=None,occurred_at=None,serialized_unit_ids=None):
        quantity=Decimal(quantity)
        if quantity<=0: raise StockControlError('Damage/loss quantity must be positive')
        if not reason.strip(): raise StockControlError('Damage/loss reason is required')
        if source_type is None: self._serialized_out(branch_id=branch_id,item_id=item_id,quantity=quantity,unit_ids=serialized_unit_ids,status='DAMAGED')
        row=DamageLossRecord(branch_id=branch_id,item_id=item_id,quantity=quantity,reason=reason,source_type=source_type,source_id=source_id,approved_by=user_id)
        self.session.add(row); self.session.flush()
        when=occurred_at or datetime.now(timezone.utc)
        result=self.fifo.consume(branch_id=branch_id,item_id=item_id,quantity=quantity,source_type='DAMAGE_LOSS',source_id=row.id,occurred_at=when,reason=reason)
        self.session.add(AuditLog(branch_id=branch_id,actor_user_id=user_id,action_type='DAMAGE_LOSS',entity_type='DAMAGE_LOSS',entity_id=row.id,timestamp=when,reason=reason,after_json={'quantity':str(quantity),'fifo_cost':str(result.total_cost)}))
        self.session.flush(); return row,result
