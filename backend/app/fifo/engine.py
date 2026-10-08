from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import FifoAllocation, PurchaseLot, StockMovement


ZERO = Decimal("0")


from app.fifo.result import AllocationResult


class FifoEngine:
    """Transactional FIFO allocator.

    Positive stock movements create/consume purchase-lot lineage. A negative
    stock movement is allowed to remain temporarily uncosted; later purchases
    deterministically reconcile the oldest unresolved negative consumption.
    """

    def __init__(self, session: Session):
        self.session = session

    def create_purchase_lot(
        self,
        *,
        branch_id: uuid.UUID,
        purchase_line_id: uuid.UUID,
        item_id: uuid.UUID,
        quantity: Decimal,
        unit_cost: Decimal,
        lot_date: date,
        movement_source_id: uuid.UUID,
        occurred_at: datetime | None = None,
        create_stock_movement: bool = True,
    ) -> PurchaseLot:
        if quantity <= ZERO:
            raise ValueError("Purchase quantity must be greater than zero")
        if unit_cost < ZERO:
            raise ValueError("Purchase cost cannot be negative")

        now = occurred_at or datetime.now(timezone.utc)
        lot = PurchaseLot(
            branch_id=branch_id,
            purchase_line_id=purchase_line_id,
            item_id=item_id,
            original_quantity=quantity,
            remaining_quantity=quantity,
            unit_cost=unit_cost,
            lot_date=lot_date,
            is_closed=False,
        )
        self.session.add(lot)
        self.session.flush()

        if create_stock_movement:
            movement = StockMovement(
                branch_id=branch_id,
                item_id=item_id,
                source_type="PURCHASE",
                source_id=movement_source_id,
                quantity_delta=quantity,
                occurred_at=now,
            )
            self.session.add(movement)
            self.session.flush()

        # First consume the oldest unresolved negative stock, then the new
        # lot's remaining quantity becomes available for future FIFO sales.
        self._reconcile_negative_stock(
            branch_id=branch_id,
            item_id=item_id,
            lot=lot,
            as_of=now,
        )
        return lot

    def consume(
        self,
        *,
        branch_id: uuid.UUID,
        item_id: uuid.UUID,
        quantity: Decimal,
        source_type: str,
        source_id: uuid.UUID,
        occurred_at: datetime | None = None,
        reason: str | None = None,
    ) -> AllocationResult:
        if quantity <= ZERO:
            raise ValueError("Consumption quantity must be greater than zero")
        now = occurred_at or datetime.now(timezone.utc)
        movement = StockMovement(
            branch_id=branch_id,
            item_id=item_id,
            source_type=source_type,
            source_id=source_id,
            quantity_delta=-quantity,
            occurred_at=now,
            reason=reason,
        )
        self.session.add(movement)
        self.session.flush()

        remaining = quantity
        total_cost = ZERO
        allocated = ZERO

        # Positive physical adjustments are represented as cost pools with no
        # purchase-lot identity. They are consumed only after true purchase
        # lots so purchase FIFO remains authoritative.
        pools = list(self.session.scalars(
            select(FifoAllocation).where(
                FifoAllocation.purchase_lot_id.is_(None),
                FifoAllocation.allocation_status == "ADJUSTMENT_POOL",
                FifoAllocation.stock_movement_id != movement.id,
            ).join(StockMovement, StockMovement.id == FifoAllocation.stock_movement_id).where(
                StockMovement.branch_id == branch_id, StockMovement.item_id == item_id,
                StockMovement.quantity_delta > ZERO, StockMovement.occurred_at <= now,
            ).order_by(StockMovement.occurred_at, StockMovement.id).with_for_update()
        ))

        lots = self.session.scalars(
            select(PurchaseLot)
            .where(
                PurchaseLot.branch_id == branch_id,
                PurchaseLot.item_id == item_id,
                PurchaseLot.remaining_quantity > ZERO,
                PurchaseLot.lot_date <= now.date(),
            )
            .order_by(PurchaseLot.lot_date, PurchaseLot.created_at, PurchaseLot.id)
            .with_for_update()
        ).all()

        for lot in lots:
            if remaining <= ZERO:
                break
            take = min(remaining, lot.remaining_quantity)
            lot.remaining_quantity -= take
            lot.is_closed = lot.remaining_quantity == ZERO
            allocation = FifoAllocation(
                stock_movement_id=movement.id,
                purchase_lot_id=lot.id,
                allocated_quantity=take,
                allocated_unit_cost=lot.unit_cost,
                allocation_status="ALLOCATED",
                created_at=now,
            )
            self.session.add(allocation)
            remaining -= take
            allocated += take
            total_cost += take * lot.unit_cost

        for pool in pools:
            if remaining <= ZERO:
                break
            take = min(remaining, Decimal(pool.allocated_quantity))
            unit_cost = Decimal(pool.allocated_unit_cost or ZERO)
            pool.allocated_quantity -= take
            if pool.allocated_quantity == ZERO:
                self.session.delete(pool)
            self.session.add(FifoAllocation(
                stock_movement_id=movement.id, purchase_lot_id=None, allocated_quantity=take,
                allocated_unit_cost=unit_cost, allocation_status="ADJUSTMENT_ALLOCATED", created_at=now,
            ))
            remaining -= take; allocated += take; total_cost += take * unit_cost

        if remaining > ZERO:
            self.session.add(
                FifoAllocation(
                    stock_movement_id=movement.id,
                    purchase_lot_id=None,
                    allocated_quantity=remaining,
                    allocated_unit_cost=None,
                    allocation_status="NEGATIVE_STOCK",
                    created_at=now,
                )
            )

        self.session.flush()
        return AllocationResult(
            movement_id=movement.id,
            requested_quantity=quantity,
            allocated_quantity=allocated,
            negative_quantity=remaining,
            total_cost=total_cost,
        )

    def _reconcile_negative_stock(
        self,
        *,
        branch_id: uuid.UUID,
        item_id: uuid.UUID,
        lot: PurchaseLot,
        as_of: datetime,
    ) -> Decimal:
        available = lot.remaining_quantity
        if available <= ZERO:
            return ZERO

        # Only unresolved negative allocations are candidates. Ordering by the
        # original stock-consumption movement makes reconciliation deterministic.
        rows = self.session.execute(
            select(FifoAllocation, StockMovement)
            .join(StockMovement, StockMovement.id == FifoAllocation.stock_movement_id)
            .where(
                FifoAllocation.purchase_lot_id.is_(None),
                FifoAllocation.allocation_status == "NEGATIVE_STOCK",
                StockMovement.branch_id == branch_id,
                StockMovement.item_id == item_id,
                StockMovement.quantity_delta < ZERO,
                StockMovement.occurred_at <= as_of,
            )
            .order_by(StockMovement.occurred_at, StockMovement.id)
            .with_for_update()
        ).all()

        reconciled = ZERO
        for allocation, _movement in rows:
            if available <= ZERO:
                break
            take = min(available, allocation.allocated_quantity)
            # Preserve the unresolved allocation as a reduced remainder; the
            # reconciled portion is represented by a new lineage row.
            allocation.allocated_quantity -= take
            replacement = FifoAllocation(
                stock_movement_id=allocation.stock_movement_id,
                purchase_lot_id=lot.id,
                allocated_quantity=take,
                allocated_unit_cost=lot.unit_cost,
                allocation_status="RECONCILED",
                created_at=as_of,
            )
            self.session.add(replacement)
            available -= take
            reconciled += take
            if allocation.allocated_quantity == ZERO:
                self.session.delete(allocation)

        lot.remaining_quantity = available
        lot.is_closed = available == ZERO
        self.session.flush()
        return reconciled

