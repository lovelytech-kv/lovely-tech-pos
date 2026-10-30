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
    def damage_loss(self, *, branch_id,item_id,quantity,reason,user_id,source_type=None,source_id=None,occurred_at=None,serialized_unit_ids=None,loss_type="DAMAGE"):
        quantity=Decimal(quantity)
        if quantity<=0: raise StockControlError('Damage/loss quantity must be positive')
        if not reason.strip(): raise StockControlError('Damage/loss reason is required')
        if source_type is None: self._serialized_out(branch_id=branch_id,item_id=item_id,quantity=quantity,unit_ids=serialized_unit_ids,status='DAMAGED')
        row=DamageLossRecord(branch_id=branch_id,item_id=item_id,quantity=quantity,reason=reason,source_type=source_type,source_id=source_id,approved_by=user_id,loss_type=loss_type)
        self.session.add(row); self.session.flush()
        when=occurred_at or datetime.now(timezone.utc)
        result=self.fifo.consume(branch_id=branch_id,item_id=item_id,quantity=quantity,source_type='DAMAGE_LOSS',source_id=row.id,occurred_at=when,reason=reason)
        self.session.add(AuditLog(branch_id=branch_id,actor_user_id=user_id,action_type='DAMAGE_LOSS',entity_type='DAMAGE_LOSS',entity_id=row.id,timestamp=when,reason=reason,after_json={'quantity':str(quantity),'fifo_cost':str(result.total_cost),'loss_type':loss_type}))
        self.session.flush(); return row,result
    def restock_damage(self, *, damage_id, branch_id, user_id, reason):
        """Requirements 07: if a damaged/lost item is resellable, Admin reverses the damage through an audited restock.
        History is kept: the damage record becomes RESTOCKED and a positive DAMAGE_RESTOCK movement is added at the cost
        the damage was booked at (or the latest lot cost when no cost was booked, e.g. a damaged return)."""
        if not (reason or '').strip(): raise StockControlError('Restock reason is required')
        rec=self.session.scalar(select(DamageLossRecord).where(DamageLossRecord.id==damage_id,DamageLossRecord.branch_id==branch_id).with_for_update())
        if rec is None: raise StockControlError('Damage/loss record not found')
        if rec.review_status not in ('APPROVED','PENDING'): raise StockControlError(f'Only an open damage/loss record can be restocked (status {rec.review_status})')
        item=self.session.get(Item,rec.item_id)
        if item is not None and self._is_serialized(item):
            raise StockControlError('IMEI-tracked phones cannot be restocked from a damage record: enter the phone again in Purchases with its IMEI')
        qty=Decimal(rec.quantity); now=datetime.now(timezone.utc); prior_status=rec.review_status
        unit_cost=None
        loss_mv=self.session.scalar(select(StockMovement).where(StockMovement.source_type=='DAMAGE_LOSS',StockMovement.source_id==rec.id))
        if loss_mv is not None:
            allocs=[a for a in self.session.scalars(select(FifoAllocation).where(FifoAllocation.stock_movement_id==loss_mv.id)).all() if a.allocated_unit_cost is not None]
            booked=sum((Decimal(a.allocated_quantity)*Decimal(a.allocated_unit_cost) for a in allocs),Decimal('0'))
            if allocs and qty>0: unit_cost=(booked/qty)
        if unit_cost is None:
            latest=self.session.scalar(select(PurchaseLot).where(PurchaseLot.branch_id==branch_id,PurchaseLot.item_id==rec.item_id).order_by(PurchaseLot.lot_date.desc(),PurchaseLot.created_at.desc()).limit(1))
            if latest is None: raise StockControlError('This item has no completed purchase cost yet: complete the purchase cost first (Purchase Cost Pending), then restock')
            unit_cost=Decimal(latest.unit_cost)
        mv=StockMovement(branch_id=branch_id,item_id=rec.item_id,source_type='DAMAGE_RESTOCK',source_id=rec.id,quantity_delta=qty,occurred_at=now,reason=reason.strip())
        self.session.add(mv); self.session.flush()
        self.session.add(FifoAllocation(stock_movement_id=mv.id,purchase_lot_id=None,allocated_quantity=qty,allocated_unit_cost=unit_cost.quantize(Decimal('0.0001')),allocation_status='ADJUSTMENT_POOL',created_at=now))
        rec.review_status='RESTOCKED'; rec.version+=1
        self.session.add(AuditLog(branch_id=branch_id,actor_user_id=user_id,action_type='DAMAGE_RESTOCK',entity_type='DAMAGE_LOSS',entity_id=rec.id,timestamp=now,reason=reason.strip(),before_json={'review_status':prior_status},after_json={'review_status':'RESTOCKED','quantity':str(qty),'unit_cost':str(unit_cost)}))
        self.session.flush(); return rec
