from decimal import Decimal

from app.fifo.engine import AllocationResult


def test_fifo_result_is_fully_costed_when_no_negative_stock():
    result = AllocationResult(
        movement_id=__import__("uuid").uuid4(),
        requested_quantity=Decimal("7"),
        allocated_quantity=Decimal("7"),
        negative_quantity=Decimal("0"),
        total_cost=Decimal("5800"),
    )
    assert result.fully_costed
    assert result.total_cost == Decimal("5800")


def test_fifo_result_flags_negative_stock():
    result = AllocationResult(
        movement_id=__import__("uuid").uuid4(),
        requested_quantity=Decimal("7"),
        allocated_quantity=Decimal("5"),
        negative_quantity=Decimal("2"),
        total_cost=Decimal("4000"),
    )
    assert not result.fully_costed
