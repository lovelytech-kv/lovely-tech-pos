from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal("0")


@dataclass(frozen=True)
class AllocationResult:
    movement_id: uuid.UUID
    requested_quantity: Decimal
    allocated_quantity: Decimal
    negative_quantity: Decimal
    total_cost: Decimal

    @property
    def fully_costed(self) -> bool:
        return self.negative_quantity == ZERO
