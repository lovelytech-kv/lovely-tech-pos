from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.inventory import PurchaseLine, PurchaseLot, FifoAllocation, StockMovement
from app.models.security import AuditLog
from app.models.sales import Sale, SaleLine, RepairPart
from app.fifo.replay import FifoReplayService, FifoReplayError


class PurchaseCorrectionError(ValueError):
    pass


_COST_ALLOCATION_STATUSES = {"ALLOCATED", "RECONCILED", "RETURN_RESTORED", "REPAIR_RETURN"}


def recalculate_dependent_costs(session: Session, lot_id, new_cost: Decimal) -> dict:
    """Reprice every persisted FIFO allocation belonging to one purchase lot.

    Quantity lineage is deliberately untouched. Only the cost value flowing from
    the corrected lot is recalculated, then denormalized document totals are
    refreshed so reports remain consistent.
    """
    allocations = list(session.scalars(
        select(FifoAllocation).where(
            FifoAllocation.purchase_lot_id == lot_id,
            FifoAllocation.allocation_status.in_(_COST_ALLOCATION_STATUSES),
        ).with_for_update()
    ))
    affected_sales: set = set()
    affected_repairs: set = set()
    changed_quantity = Decimal("0")
    for allocation in allocations:
        allocation.allocated_unit_cost = Decimal(new_cost)
        changed_quantity += Decimal(allocation.allocated_quantity)
        movement = session.scalar(select(StockMovement).where(StockMovement.id == allocation.stock_movement_id))
        if movement is None:
            continue
        if movement.source_type == "SALE":
            line = session.scalar(select(SaleLine).where(SaleLine.id == movement.source_id))
            if line:
                affected_sales.add(line.sale_id)
        elif movement.source_type == "REPAIR_PART":
            affected_repairs.add(movement.source_id)

    # Refresh every affected sale from its actual FIFO allocations.
    for sale_id in affected_sales:
        sale = session.scalar(select(Sale).where(Sale.id == sale_id).with_for_update())
        if not sale:
            continue
        line_ids = list(session.scalars(select(SaleLine.id).where(SaleLine.sale_id == sale.id)))
        movement_ids = list(session.scalars(select(StockMovement.id).where(StockMovement.source_type == "SALE", StockMovement.source_id.in_(line_ids))))
        sale_cost = session.scalar(
            select(func.coalesce(func.sum(FifoAllocation.allocated_quantity * FifoAllocation.allocated_unit_cost), 0))
            .where(FifoAllocation.stock_movement_id.in_(movement_ids), FifoAllocation.allocated_unit_cost.is_not(None))
        ) if movement_ids else Decimal("0")
        sale.total_cost = Decimal(sale_cost or 0).quantize(Decimal("0.01"))

    # RepairPart stores its FIFO cost as a denormalized field for quick display.
    for movement_id in affected_repairs:
        part = session.scalar(select(RepairPart).where(RepairPart.stock_movement_id == movement_id).with_for_update())
        if not part:
            continue
        total = session.scalar(
            select(func.coalesce(func.sum(FifoAllocation.allocated_quantity * FifoAllocation.allocated_unit_cost), 0))
            .where(FifoAllocation.stock_movement_id == movement_id, FifoAllocation.allocated_unit_cost.is_not(None))
        )
        part.fifo_cost = Decimal(total or 0).quantize(Decimal("0.01"))

    session.flush()
    return {"allocation_count": len(allocations), "quantity": changed_quantity, "sale_count": len(affected_sales), "repair_part_count": len(affected_repairs)}


class PurchaseCorrectionService:
    def __init__(self, session: Session):
        self.session = session

    def change_cost(self, *, purchase_line: PurchaseLine, new_cost: Decimal, reason: str, actor_user_id=None):
        if new_cost < 0:
            raise PurchaseCorrectionError("Purchase cost cannot be negative")
        if not reason.strip():
            raise PurchaseCorrectionError("Correction reason is required")
        lot = self.session.scalar(
            select(PurchaseLot).where(PurchaseLot.purchase_line_id == purchase_line.id).with_for_update()
        )
        if lot is None:
            raise PurchaseCorrectionError("Purchase lot not found")
        old = Decimal(lot.unit_cost)
        if old == Decimal(new_cost):
            raise PurchaseCorrectionError("Purchase cost is already the requested value")
        allocation_exists = self.session.scalar(
            select(FifoAllocation.id).where(
                FifoAllocation.purchase_lot_id == lot.id,
                FifoAllocation.allocation_status.in_(_COST_ALLOCATION_STATUSES),
            ).limit(1)
        ) is not None
        lot.unit_cost = Decimal(new_cost)
        purchase_line.unit_cost = Decimal(new_cost)
        recalculation = recalculate_dependent_costs(self.session, lot.id, Decimal(new_cost)) if allocation_exists else {
            "allocation_count": 0, "quantity": Decimal("0"), "sale_count": 0, "repair_part_count": 0
        }
        if actor_user_id:
            self.session.add(AuditLog(
                branch_id=lot.branch_id, actor_user_id=actor_user_id,
                action_type="PURCHASE_COST_RECALCULATED" if allocation_exists else "PURCHASE_COST_CORRECTED",
                entity_type="PURCHASE_LINE", entity_id=purchase_line.id,
                timestamp=datetime.now(timezone.utc), reason=reason,
                before_json={"unit_cost": str(old)},
                after_json={"unit_cost": str(new_cost), **{k: str(v) for k, v in recalculation.items() if k == "quantity"}},
                source_transaction_id=purchase_line.id,
            ))
        self.session.flush()
        return old, lot, recalculation


    def change_quantity(self, *, purchase_line: PurchaseLine, new_quantity: Decimal, reason: str, actor_user_id=None):
        if new_quantity <= 0:
            raise PurchaseCorrectionError("Purchase quantity must be greater than zero")
        if not reason.strip():
            raise PurchaseCorrectionError("Correction reason is required")
        line = self.session.scalar(select(PurchaseLine).where(PurchaseLine.id == purchase_line.id).with_for_update())
        lot = self.session.scalar(select(PurchaseLot).where(PurchaseLot.purchase_line_id == purchase_line.id).with_for_update())
        if line is None or lot is None:
            raise PurchaseCorrectionError("Purchase line/lot not found")
        old = Decimal(line.quantity); new = Decimal(new_quantity)
        if old == new:
            raise PurchaseCorrectionError("Purchase quantity is already the requested value")
        consumed = old - Decimal(lot.remaining_quantity)
        if new < consumed:
            raise PurchaseCorrectionError("Quantity cannot be reduced below quantity already consumed by FIFO")
        now = datetime.now(timezone.utc)
        delta = new - old
        if delta > 0:
            line.quantity = new; lot.original_quantity = new; lot.remaining_quantity = Decimal(lot.remaining_quantity) + delta
            movement = StockMovement(branch_id=lot.branch_id, item_id=lot.item_id, source_type="PURCHASE_CORRECTION", source_id=line.id, quantity_delta=delta, occurred_at=now, reason=reason)
            self.session.add(movement); self.session.flush()
            # New quantity first reconciles older negative stock before becoming available FIFO.
            self._reconcile_new_purchase_quantity(lot, delta, now)
            recalculate_dependent_costs(self.session, lot.id, lot.unit_cost)
        else:
            reduce_qty = -delta
            line.quantity = new; lot.original_quantity = new
            lot.remaining_quantity = Decimal(lot.remaining_quantity) - reduce_qty
            lot.is_closed = lot.remaining_quantity == 0
            movement = StockMovement(branch_id=lot.branch_id, item_id=lot.item_id, source_type="PURCHASE_CORRECTION", source_id=line.id, quantity_delta=-reduce_qty, occurred_at=now, reason=reason)
            self.session.add(movement); self.session.flush()
            self.session.add(FifoAllocation(stock_movement_id=movement.id, purchase_lot_id=lot.id, allocated_quantity=reduce_qty, allocated_unit_cost=lot.unit_cost, allocation_status="PURCHASE_QUANTITY_CORRECTION", created_at=now))
        if actor_user_id:
            self.session.add(AuditLog(branch_id=lot.branch_id, actor_user_id=actor_user_id, action_type="PURCHASE_QUANTITY_CORRECTED", entity_type="PURCHASE_LINE", entity_id=line.id, timestamp=now, reason=reason, before_json={"quantity":str(old)}, after_json={"quantity":str(new)}, source_transaction_id=line.id))
        self.session.flush()
        return old, new, lot

    def _reconcile_new_purchase_quantity(self, lot: PurchaseLot, quantity: Decimal, as_of: datetime):
        # Reuse the same deterministic negative-stock ordering as a normal purchase.
        from app.fifo.engine import FifoEngine
        FifoEngine(self.session)._reconcile_negative_stock(branch_id=lot.branch_id, item_id=lot.item_id, lot=lot, as_of=as_of)

    def change_date(self, *, purchase_line: PurchaseLine, new_date: date, reason: str, actor_user_id=None):
        if not reason.strip():
            raise PurchaseCorrectionError("Correction reason is required")
        lot = self.session.scalar(select(PurchaseLot).where(PurchaseLot.purchase_line_id == purchase_line.id).with_for_update())
        if lot is None:
            raise PurchaseCorrectionError("Purchase lot not found")
        allocations = self.session.scalar(
            select(FifoAllocation.id).where(FifoAllocation.purchase_lot_id == lot.id, FifoAllocation.allocation_status.in_(_COST_ALLOCATION_STATUSES)).limit(1)
        )
        old = lot.lot_date
        if allocations is not None:
            try:
                # The correction is safe only when every positive stock movement for
                # this item is purchase-backed. Otherwise replay would lose return /
                # replacement / adjustment lineage and is deliberately rejected.
                if not __import__('app.fifo.replay', fromlist=['can_replay_purchase_fifo']).can_replay_purchase_fifo(self.session, branch_id=lot.branch_id, item_id=lot.item_id):
                    raise PurchaseCorrectionError("Purchase date correction is blocked because non-purchase stock lineage exists for this item")
                lot.lot_date = new_date
                purchase_line.line_date = new_date
                FifoReplayService(self.session).replay_item(branch_id=lot.branch_id, item_id=lot.item_id, reason=reason)
            except FifoReplayError as exc:
                lot.lot_date = old
                raise PurchaseCorrectionError(str(exc)) from exc
        else:
            lot.lot_date = new_date
            purchase_line.line_date = new_date
        if actor_user_id:
            self.session.add(AuditLog(branch_id=lot.branch_id, actor_user_id=actor_user_id, action_type="PURCHASE_DATE_CORRECTED", entity_type="PURCHASE_LINE", entity_id=purchase_line.id, timestamp=datetime.now(timezone.utc), reason=reason, before_json={"line_date": old.isoformat()}, after_json={"line_date": new_date.isoformat()}, source_transaction_id=purchase_line.id))
        self.session.flush()
        return old, lot
