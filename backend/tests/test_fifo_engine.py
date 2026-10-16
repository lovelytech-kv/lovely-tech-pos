import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.fifo.engine import AllocationResult, FifoEngine
from app.models.inventory import FifoAllocation, PurchaseLot, StockMovement
from app.models.master import Branch, Category, Item, ItemType


def _setup_test_db(tmp_path):
    """Create isolated in-memory SQLite database with tables."""
    db_path = tmp_path / "fifo_test.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(64) NOT NULL)"
        )
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": "0036_import_batch_idempotency"},
        )
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine, Session


def _create_master_data(session):
    """Create required master data."""
    branch = Branch(code="TST", name="Test Branch", is_active=True)
    session.add(branch)
    category = Category(name="Test Cat", is_active=True)
    session.add(category)
    item_type = ItemType(code="STD", name="Standard", is_active=True, is_serialized=False)
    session.add(item_type)
    session.flush()
    item = Item(
        item_code="ITEM001",
        description="Test Item",
        category_id=category.id,
        item_type_id=item_type.id,
        is_active=True,
    )
    session.add(item)
    session.flush()
    session.commit()
    return branch, category, item_type, item


@pytest.fixture
def fifo_test_env(tmp_path, monkeypatch):
    import app.core.config as config

    monkeypatch.setattr(config.settings, "app_env", "test")
    monkeypatch.setattr(config.settings, "sqlite_bootstrap_fallback_enabled", True)
    engine, Session = _setup_test_db(tmp_path)
    session = Session()
    try:
        branch, category, item_type, item = _create_master_data(session)
        yield {
            "engine": engine,
            "Session": Session,
            "session": session,
            "branch": branch,
            "item": item,
        }
    finally:
        session.close()
        engine.dispose()


def test_fifo_result_is_fully_costed_when_no_negative_stock():
    result = AllocationResult(
        movement_id=uuid.uuid4(),
        requested_quantity=Decimal("7"),
        allocated_quantity=Decimal("7"),
        negative_quantity=Decimal("0"),
        total_cost=Decimal("5800"),
    )
    assert result.fully_costed
    assert result.total_cost == Decimal("5800")


def test_fifo_result_flags_negative_stock():
    result = AllocationResult(
        movement_id=uuid.uuid4(),
        requested_quantity=Decimal("7"),
        allocated_quantity=Decimal("5"),
        negative_quantity=Decimal("2"),
        total_cost=Decimal("4000"),
    )
    assert not result.fully_costed


def test_fifo_consumes_multiple_lots_in_fifo_order(fifo_test_env):
    branch = fifo_test_env["branch"]
    item = fifo_test_env["item"]
    Session = fifo_test_env["Session"]

    session = Session()
    try:
        engine = FifoEngine(session)
        lot1 = engine.create_purchase_lot(
            branch_id=branch.id,
            purchase_line_id=uuid.uuid4(),
            item_id=item.id,
            quantity=Decimal("10"),
            unit_cost=Decimal("100.00"),
            lot_date=date(2024, 1, 1),
            movement_source_id=uuid.uuid4(),
        )
        session.commit()
        lot2 = engine.create_purchase_lot(
            branch_id=branch.id,
            purchase_line_id=uuid.uuid4(),
            item_id=item.id,
            quantity=Decimal("10"),
            unit_cost=Decimal("200.00"),
            lot_date=date(2024, 1, 2),
            movement_source_id=uuid.uuid4(),
        )
        session.commit()

        result = engine.consume(
            branch_id=branch.id,
            item_id=item.id,
            quantity=Decimal("15"),
            source_type="SALE",
            source_id=uuid.uuid4(),
        )
        session.commit()

        session.refresh(lot1)
        session.refresh(lot2)
        assert lot1.remaining_quantity == Decimal("0")
        assert lot1.is_closed is True
        assert lot2.remaining_quantity == Decimal("5")
        assert lot2.is_closed is False
        assert result.allocated_quantity == Decimal("15")
        assert result.negative_quantity == Decimal("0")
        assert result.total_cost == (Decimal("10") * Decimal("100.00")) + (Decimal("5") * Decimal("200.00"))
    finally:
        session.close()


def test_lot_remaining_quantity_decreases_and_closes(fifo_test_env):
    branch = fifo_test_env["branch"]
    item = fifo_test_env["item"]
    Session = fifo_test_env["Session"]

    session = Session()
    try:
        engine = FifoEngine(session)
        lot = engine.create_purchase_lot(
            branch_id=branch.id,
            purchase_line_id=uuid.uuid4(),
            item_id=item.id,
            quantity=Decimal("10"),
            unit_cost=Decimal("50.00"),
            lot_date=date(2024, 1, 1),
            movement_source_id=uuid.uuid4(),
        )
        session.commit()
        session.refresh(lot)
        assert lot.remaining_quantity == Decimal("10")
        assert lot.is_closed is False

        result = engine.consume(
            branch_id=branch.id,
            item_id=item.id,
            quantity=Decimal("10"),
            source_type="SALE",
            source_id=uuid.uuid4(),
        )
        session.commit()
        session.refresh(lot)
        assert lot.remaining_quantity == Decimal("0")
        assert lot.is_closed is True
        assert result.negative_quantity == Decimal("0")
        assert result.fully_costed
    finally:
        session.close()


def test_consume_exceeds_stock_creates_negative_allocation(fifo_test_env):
    branch = fifo_test_env["branch"]
    item = fifo_test_env["item"]
    Session = fifo_test_env["Session"]

    session = Session()
    try:
        engine = FifoEngine(session)
        lot = engine.create_purchase_lot(
            branch_id=branch.id,
            purchase_line_id=uuid.uuid4(),
            item_id=item.id,
            quantity=Decimal("5"),
            unit_cost=Decimal("100.00"),
            lot_date=date(2024, 1, 1),
            movement_source_id=uuid.uuid4(),
        )
        session.commit()

        sale_id = uuid.uuid4()
        result = engine.consume(
            branch_id=branch.id,
            item_id=item.id,
            quantity=Decimal("10"),
            source_type="SALE",
            source_id=sale_id,
        )
        session.commit()

        assert result.requested_quantity == Decimal("10")
        assert result.allocated_quantity == Decimal("5")
        assert result.negative_quantity == Decimal("5")
        assert result.fully_costed is False
        assert result.total_cost == Decimal("500.00")

        session.refresh(lot)
        assert lot.remaining_quantity == Decimal("0")
        assert lot.is_closed is True

        neg_alloc = session.query(FifoAllocation).filter(
            FifoAllocation.stock_movement_id == result.movement_id,
            FifoAllocation.allocation_status == "NEGATIVE_STOCK",
        ).first()
        assert neg_alloc is not None
        assert neg_alloc.allocated_quantity == Decimal("5")
        assert neg_alloc.allocated_unit_cost is None
        assert neg_alloc.purchase_lot_id is None
    finally:
        session.close()


def test_later_purchase_reconciles_oldest_negative_allocation_first(fifo_test_env):
    branch = fifo_test_env["branch"]
    item = fifo_test_env["item"]
    Session = fifo_test_env["Session"]

    session = Session()
    try:
        engine = FifoEngine(session)
        # First sale creates negative allocation
        result1 = engine.consume(
            branch_id=branch.id,
            item_id=item.id,
            quantity=Decimal("3"),
            source_type="SALE",
            source_id=uuid.uuid4(),
        )
        session.commit()
        assert result1.negative_quantity == Decimal("3")
        neg_movement_id1 = result1.movement_id

        # Second sale creates another negative allocation (older one is result1 by movement occurred_at)
        result2 = engine.consume(
            branch_id=branch.id,
            item_id=item.id,
            quantity=Decimal("2"),
            source_type="SALE",
            source_id=uuid.uuid4(),
        )
        session.commit()
        assert result2.negative_quantity == Decimal("2")
        neg_movement_id2 = result2.movement_id

        # Now purchase lot comes in - should reconcile oldest unresolved negative first (result1)
        now = datetime.now(timezone.utc)
        lot = engine.create_purchase_lot(
            branch_id=branch.id,
            purchase_line_id=uuid.uuid4(),
            item_id=item.id,
            quantity=Decimal("5"),
            unit_cost=Decimal("150.00"),
            lot_date=date(2024, 1, 5),
            movement_source_id=uuid.uuid4(),
            occurred_at=now,
        )
        session.commit()

        # Check reconciliation - first negative should be fully reconciled, second partially
        neg1_allocs = session.query(FifoAllocation).filter(
            FifoAllocation.stock_movement_id == neg_movement_id1
        ).all()
        # After full reconciliation, original negative allocation should be deleted and replaced by RECONCILED
        reconciled1 = [a for a in neg1_allocs if a.allocation_status == "RECONCILED"]
        remaining1 = [a for a in neg1_allocs if a.allocation_status == "NEGATIVE_STOCK"]
        assert len(reconciled1) >= 1  # reconciled portion
        # First negative (qty 3) should be fully reconciled by first part of lot
        total_reconciled_for_m1 = sum(a.allocated_quantity for a in reconciled1)
        assert total_reconciled_for_m1 == Decimal("3")
        assert len(remaining1) == 0  # fully consumed

        # Second negative (qty 2) - lot had 5 total, used 3 for first, so 2 left for second
        neg2_allocs = session.query(FifoAllocation).filter(
            FifoAllocation.stock_movement_id == neg_movement_id2
        ).all()
        reconciled2 = [a for a in neg2_allocs if a.allocation_status == "RECONCILED"]
        remaining2 = [a for a in neg2_allocs if a.allocation_status == "NEGATIVE_STOCK"]
        total_recon2 = sum(a.allocated_quantity for a in reconciled2)
        assert total_recon2 == Decimal("2")
        assert len(remaining2) == 0  # fully reconciled

        session.refresh(lot)
        assert lot.remaining_quantity == Decimal("0")
        assert lot.is_closed is True
    finally:
        session.close()


def test_reconciliation_preserves_lot_properties_and_creates_lineage(fifo_test_env):
    branch = fifo_test_env["branch"]
    item = fifo_test_env["item"]
    Session = fifo_test_env["Session"]

    session = Session()
    try:
        engine = FifoEngine(session)
        # Create negative allocation
        result = engine.consume(
            branch_id=branch.id,
            item_id=item.id,
            quantity=Decimal("5"),
            source_type="SALE",
            source_id=uuid.uuid4(),
        )
        session.commit()
        neg_movement_id = result.movement_id

        # Purchase lot comes in
        lot = engine.create_purchase_lot(
            branch_id=branch.id,
            purchase_line_id=uuid.uuid4(),
            item_id=item.id,
            quantity=Decimal("10"),
            unit_cost=Decimal("75.00"),
            lot_date=date(2024, 2, 1),
            movement_source_id=uuid.uuid4(),
        )
        session.commit()

        # Check - original lot quantity preserved conceptually (original_quantity is set)
        session.refresh(lot)
        assert lot.original_quantity == Decimal("10")
        assert lot.unit_cost == Decimal("75.00")
        assert lot.remaining_quantity == Decimal("5")  # 10 - 5 reconciled
        assert lot.is_closed is False

        # Check reconciled allocations exist with correct lineage
        reconciled_allocs = session.query(FifoAllocation).filter(
            FifoAllocation.stock_movement_id == neg_movement_id,
            FifoAllocation.allocation_status == "RECONCILED",
        ).all()
        assert len(reconciled_allocs) == 1
        rec = reconciled_allocs[0]
        assert rec.purchase_lot_id == lot.id
        assert rec.allocated_quantity == Decimal("5")
        assert rec.allocated_unit_cost == Decimal("75.00")

        # Original negative allocation should be deleted
        neg_allocs = session.query(FifoAllocation).filter(
            FifoAllocation.stock_movement_id == neg_movement_id,
            FifoAllocation.allocation_status == "NEGATIVE_STOCK",
        ).all()
        assert len(neg_allocs) == 0
    finally:
        session.close()


def test_repeating_reconciliation_does_not_reconcile_same_shortage_twice(fifo_test_env):
    branch = fifo_test_env["branch"]
    item = fifo_test_env["item"]
    Session = fifo_test_env["Session"]

    session = Session()
    try:
        engine = FifoEngine(session)
        # Create negative allocation
        result = engine.consume(
            branch_id=branch.id,
            item_id=item.id,
            quantity=Decimal("3"),
            source_type="SALE",
            source_id=uuid.uuid4(),
        )
        session.commit()
        neg_movement_id = result.movement_id

        # First purchase reconciles
        lot1 = engine.create_purchase_lot(
            branch_id=branch.id,
            purchase_line_id=uuid.uuid4(),
            item_id=item.id,
            quantity=Decimal("5"),
            unit_cost=Decimal("100.00"),
            lot_date=date(2024, 3, 1),
            movement_source_id=uuid.uuid4(),
        )
        session.commit()

        # Check reconciliation happened
        reconciled = session.query(FifoAllocation).filter(
            FifoAllocation.stock_movement_id == neg_movement_id,
            FifoAllocation.allocation_status == "RECONCILED",
        ).all()
        assert len(reconciled) == 1
        assert sum(r.allocated_quantity for r in reconciled) == Decimal("3")

        # Second purchase comes in - should not reconcile the same shortage again
        lot2 = engine.create_purchase_lot(
            branch_id=branch.id,
            purchase_line_id=uuid.uuid4(),
            item_id=item.id,
            quantity=Decimal("5"),
            unit_cost=Decimal("120.00"),
            lot_date=date(2024, 3, 2),
            movement_source_id=uuid.uuid4(),
        )
        session.commit()

        # Reconciled allocations for the original negative movement should remain the same count
        reconciled_after = session.query(FifoAllocation).filter(
            FifoAllocation.stock_movement_id == neg_movement_id,
            FifoAllocation.allocation_status == "RECONCILED",
        ).all()
        assert len(reconciled_after) == 1  # Still only 1 reconciled allocation record
        assert sum(r.allocated_quantity for r in reconciled_after) == Decimal("3")

        session.refresh(lot1)
        session.refresh(lot2)
        assert lot1.remaining_quantity == Decimal("2")  # 5-3 reconciled
        assert lot2.remaining_quantity == Decimal("5")  # untouched - no double reconciliation
    finally:
        session.close()