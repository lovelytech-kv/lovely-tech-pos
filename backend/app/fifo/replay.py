from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import FifoAllocation, PurchaseLot, StockMovement

ZERO = Decimal("0")

class FifoReplayError(ValueError):
    pass

@dataclass(frozen=True)
class ReplayResult:
    item_id: uuid.UUID
    negative_movements: int
    allocated_quantity: Decimal
    unresolved_quantity: Decimal
    affected_lots: int


def can_replay_purchase_fifo(session: Session, *, branch_id, item_id) -> bool:
    """Replay is safe only when positive stock is represented exclusively by purchase lots.

    Return/replacement/adjustment positive movements have their own lineage semantics and
    must not be silently converted into purchase-lot FIFO during a correction.
    """
    positive_non_purchase = session.scalar(
        select(StockMovement.id).where(
            StockMovement.branch_id == branch_id,
            StockMovement.item_id == item_id,
            StockMovement.quantity_delta > ZERO,
            StockMovement.source_type != "PURCHASE",
        ).limit(1)
    )
    return positive_non_purchase is None


class FifoReplayService:
    """Deterministically rebuild FIFO allocations for one item.

    This is intentionally conservative: it refuses items whose positive stock
    includes non-purchase movements because those movements need their own
    lineage-aware replay rules.
    """
    def __init__(self, session: Session):
        self.session = session

    def replay_item(self, *, branch_id, item_id, reason: str) -> ReplayResult:
        if not reason.strip():
            raise FifoReplayError("Replay reason is required")
        if not can_replay_purchase_fifo(self.session, branch_id=branch_id, item_id=item_id):
            raise FifoReplayError("FIFO replay is blocked because the item has non-purchase positive stock movements")

        lots = list(self.session.scalars(
            select(PurchaseLot).where(
                PurchaseLot.branch_id == branch_id,
                PurchaseLot.item_id == item_id,
            ).order_by(PurchaseLot.lot_date, PurchaseLot.created_at, PurchaseLot.id).with_for_update()
        ))
        movements = list(self.session.scalars(
            select(StockMovement).where(
                StockMovement.branch_id == branch_id,
                StockMovement.item_id == item_id,
                StockMovement.quantity_delta < ZERO,
            ).order_by(StockMovement.occurred_at, StockMovement.id).with_for_update()
        ))

        # Reset purchase lots and remove old consumption allocations.
        for lot in lots:
            lot.remaining_quantity = lot.original_quantity
            lot.is_closed = False
        old_allocations = list(self.session.scalars(
            select(FifoAllocation).join(StockMovement, StockMovement.id == FifoAllocation.stock_movement_id).where(
                StockMovement.branch_id == branch_id,
                StockMovement.item_id == item_id,
                StockMovement.quantity_delta < ZERO,
            ).with_for_update()
        ))
        for allocation in old_allocations:
            self.session.delete(allocation)
        self.session.flush()

        allocated_total = ZERO
        unresolved_total = ZERO
        for movement in movements:
            remaining = -Decimal(movement.quantity_delta)
            available_lots = [
                lot for lot in lots
                if lot.lot_date <= movement.occurred_at.date() and Decimal(lot.remaining_quantity) > ZERO
            ]
            for lot in available_lots:
                if remaining <= ZERO:
                    break
                take = min(remaining, Decimal(lot.remaining_quantity))
                lot.remaining_quantity -= take
                lot.is_closed = lot.remaining_quantity == ZERO
                self.session.add(FifoAllocation(
                    stock_movement_id=movement.id,
                    purchase_lot_id=lot.id,
                    allocated_quantity=take,
                    allocated_unit_cost=lot.unit_cost,
                    allocation_status="REPLAYED",
                    created_at=datetime.now(timezone.utc),
                ))
                remaining -= take
                allocated_total += take
            if remaining > ZERO:
                self.session.add(FifoAllocation(
                    stock_movement_id=movement.id,
                    purchase_lot_id=None,
                    allocated_quantity=remaining,
                    allocated_unit_cost=None,
                    allocation_status="NEGATIVE_STOCK",
                    created_at=datetime.now(timezone.utc),
                ))
                unresolved_total += remaining

        self.session.flush()
        return ReplayResult(item_id, len(movements), allocated_total, unresolved_total, len(lots))
