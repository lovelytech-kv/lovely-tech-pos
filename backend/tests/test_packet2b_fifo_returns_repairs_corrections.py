import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.fifo.engine import FifoEngine
from app.models.inventory import DamageLossRecord, FifoAllocation, Purchase, PurchaseLine, PurchaseLot, StockMovement
from app.models.master import Branch, Category, Item, ItemType, Role, User
from app.models.security import IdempotencyKey
from app.models.sales import Return, Sale, SaleLine
from app.services.numbering import NumberingService
from app.services.purchase_correction import PurchaseCorrectionError, PurchaseCorrectionService
from app.services.repairs import (
    RepairCreateRequest,
    RepairPartInput,
    RepairService,
    RepairValidationError,
)
from app.services.returns import (
    ReturnLineInput,
    ReturnRequest,
    ReturnService,
    ReturnValidationError,
)


def _next_number_sqlite(db, prefix, branch_id):
    bid = branch_id if isinstance(branch_id, uuid.UUID) else uuid.UUID(branch_id)
    row = db.execute(
        text(
            "SELECT next_value FROM document_counters "
            "WHERE prefix=:prefix AND branch_id IS NOT DISTINCT FROM :branch_id"
        ),
        {"prefix": prefix, "branch_id": bid.bytes},
    ).mappings().first()
    if row is None:
        db.execute(
            text(
                "INSERT INTO document_counters(prefix, branch_id, next_value) "
                "VALUES (:prefix, :branch_id, 2)"
            ),
            {"prefix": prefix, "branch_id": bid.bytes, "next_value": 2},
        )
        return f"{prefix}-000001"
    value = int(row["next_value"])
    db.execute(
        text(
            "UPDATE document_counters SET next_value=:next "
            "WHERE prefix=:prefix AND branch_id IS NOT DISTINCT FROM :branch_id"
        ),
        {"next": value + 1, "prefix": prefix, "branch_id": bid.bytes},
    )
    return f"{prefix}-{value:06d}"


def _setup_test_db(tmp_path):
    db_path = tmp_path / "packet2b.sqlite3"
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
        connection.exec_driver_sql(
            "CREATE TABLE document_counters ("
            "prefix VARCHAR(40) NOT NULL, "
            "branch_id BLOB NOT NULL, "
            "next_value INTEGER NOT NULL, "
            "PRIMARY KEY (prefix, branch_id))"
        )
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine, Session


@pytest.fixture
def packet2b_env(tmp_path, monkeypatch):
    engine, Session = _setup_test_db(tmp_path)
    monkeypatch.setattr(NumberingService, "next_number", staticmethod(_next_number_sqlite))
    session = Session()
    try:
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
        role = Role(code="CASHIER", name="Cashier", is_system=True)
        session.add(role)
        session.flush()
        cashier = User(
            username="cashier1",
            password_hash="x",
            display_name="Cashier",
            role_id=role.id,
            branch_id=branch.id,
            is_active=True,
        )
        admin = User(
            username="admin1",
            password_hash="x",
            display_name="Admin",
            role_id=role.id,
            branch_id=branch.id,
            is_active=True,
        )
        session.add(cashier)
        session.add(admin)
        session.commit()
        yield {
            "Session": Session,
            "session": session,
            "branch": branch,
            "item": item,
            "cashier": cashier,
            "admin": admin,
        }
    finally:
        session.close()
        engine.dispose()


def _create_purchase_line(session, branch, item, quantity, unit_cost, purchase_date, line_date):
    purchase = Purchase(
        branch_id=branch.id,
        reference_no=f"REF-{uuid.uuid4().hex[:8]}",
        purchase_date=purchase_date,
        status="PENDING_COST",
    )
    session.add(purchase)
    session.flush()
    line = PurchaseLine(
        purchase_id=purchase.id,
        item_id=item.id,
        quantity=quantity,
        unit_cost=unit_cost,
        line_date=line_date,
    )
    session.add(line)
    session.flush()
    return purchase, line


def _engine_lot(session, branch, item, line, quantity, unit_cost, lot_date, occurred_at):
    engine = FifoEngine(session)
    return engine.create_purchase_lot(
        branch_id=branch.id,
        purchase_line_id=line.id,
        item_id=item.id,
        quantity=quantity,
        unit_cost=unit_cost,
        lot_date=lot_date,
        movement_source_id=line.id,
        occurred_at=occurred_at,
    )


def _sell_from_lots(session, branch, item, cashier, now, consumed):
    total = sum(qty for _, qty in consumed)
    sale = Sale(
        branch_id=branch.id,
        invoice_no=f"INV-{uuid.uuid4().hex[:8]}",
        customer_id=None,
        sale_datetime=now,
        cashier_id=cashier.id,
        document_type="SALE",
        subtotal=total * Decimal("10"),
        discount_total=Decimal("0"),
        grand_total=total * Decimal("10"),
        total_cost=Decimal("0"),
        status="COMPLETED",
    )
    session.add(sale)
    session.flush()
    line = SaleLine(
        sale_id=sale.id,
        item_id=item.id,
        quantity=total,
        unit_price=Decimal("10"),
        discount=Decimal("0"),
        final_total=total * Decimal("10"),
    )
    session.add(line)
    session.flush()
    movement = StockMovement(
        branch_id=branch.id,
        item_id=item.id,
        source_type="SALE",
        source_id=line.id,
        quantity_delta=-total,
        occurred_at=now,
        reason="sale",
    )
    session.add(movement)
    session.flush()
    for lot, qty in consumed:
        session.add(
            FifoAllocation(
                stock_movement_id=movement.id,
                purchase_lot_id=lot.id,
                allocated_quantity=qty,
                allocated_unit_cost=lot.unit_cost,
                allocation_status="ALLOCATED",
                created_at=now,
            )
        )
        lot.remaining_quantity = Decimal(lot.remaining_quantity) - qty
        lot.is_closed = lot.remaining_quantity == 0
    session.commit()
    return sale, line, movement


def _complete_return(session, branch, cashier, sale, lines, now):
    service = ReturnService(session)
    request = ReturnRequest(
        branch_id=branch.id,
        cashier_id=cashier.id,
        original_sale_id=sale.id,
        lines=tuple(lines),
        return_datetime=now,
    )
    return service.complete(request)


def _create_repair(session, branch, cashier, now):
    service = RepairService(session)
    return service.create(
        RepairCreateRequest(branch_id=branch.id, actor_user_id=cashier.id, date_in=now)
    )


def _add_repair_part(session, branch, cashier, repair, item, quantity, charge=Decimal("0")):
    service = RepairService(session)
    return service.add_part(
        repair.id, branch.id, cashier.id,
        RepairPartInput(item_id=item.id, quantity=quantity, charge_amount=charge),
    )


def _fresh(env):
    return env["Session"]()


def test_good_return_restores_exact_fifo_lineage_without_over_restore(packet2b_env):
    session = packet2b_env["session"]
    branch = packet2b_env["branch"]
    item = packet2b_env["item"]
    cashier = packet2b_env["cashier"]
    now = datetime.now(timezone.utc)
    _, line = _create_purchase_line(session, branch, item, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), date(2024, 1, 1))
    lot = _engine_lot(session, branch, item, line, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), now)
    session.commit()

    sale, sale_line, _ = _sell_from_lots(session, branch, item, cashier, now, [(lot, Decimal("10"))])
    assert lot.remaining_quantity == Decimal("0")

    result = _complete_return(session, branch, cashier, sale, [ReturnLineInput(sale_line.id, Decimal("6"), "GOOD")], now)
    session.commit()

    check = _fresh(packet2b_env)
    try:
        restored_lot = check.get(PurchaseLot, lot.id)
        assert restored_lot.remaining_quantity == Decimal("6"), "partial return must restore only the returned quantity"
        return_movement = check.scalar(
            select(StockMovement).where(
                StockMovement.source_type == "RETURN", StockMovement.source_id == result.return_id
            )
        )
        restored = check.scalars(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == return_movement.id,
                FifoAllocation.allocation_status == "RETURN_RESTORED",
            )
        ).all()
        assert [(a.purchase_lot_id, a.allocated_quantity, a.allocated_unit_cost) for a in restored] == [
            (lot.id, Decimal("6"), Decimal("100.00"))
        ]

        result2 = _complete_return(session, branch, cashier, sale, [ReturnLineInput(sale_line.id, Decimal("4"), "GOOD")], now)
        session.commit()
        check2 = _fresh(packet2b_env)
        try:
            assert check2.get(PurchaseLot, lot.id).remaining_quantity == Decimal("10"), "full return must restore the lot to its original quantity, not beyond"
        finally:
            check2.close()

        with pytest.raises(ReturnValidationError, match="exceeds the sold quantity"):
            _complete_return(session, branch, cashier, sale, [ReturnLineInput(sale_line.id, Decimal("1"), "GOOD")], now)
    finally:
        check.close()


def test_good_return_restores_each_lot_exactly_as_sold(packet2b_env):
    session = packet2b_env["session"]
    branch = packet2b_env["branch"]
    item = packet2b_env["item"]
    cashier = packet2b_env["cashier"]
    now = datetime.now(timezone.utc)
    _, line = _create_purchase_line(session, branch, item, Decimal("20"), Decimal("100.00"), date(2024, 1, 1), date(2024, 1, 1))
    lot_a = _engine_lot(session, branch, item, line, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), now)
    lot_b = _engine_lot(session, branch, item, line, Decimal("10"), Decimal("200.00"), date(2024, 1, 2), now)
    session.commit()

    sale, sale_line, _ = _sell_from_lots(
        session, branch, item, cashier, now, [(lot_a, Decimal("6")), (lot_b, Decimal("4"))]
    )

    result = _complete_return(session, branch, cashier, sale, [ReturnLineInput(sale_line.id, Decimal("10"), "GOOD")], now)
    session.commit()

    check = _fresh(packet2b_env)
    try:
        assert check.get(PurchaseLot, lot_a.id).remaining_quantity == Decimal("10")
        assert check.get(PurchaseLot, lot_b.id).remaining_quantity == Decimal("10")
        return_movement = check.scalar(
            select(StockMovement).where(
                StockMovement.source_type == "RETURN", StockMovement.source_id == result.return_id
            )
        )
        restored = check.scalars(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == return_movement.id,
                FifoAllocation.allocation_status == "RETURN_RESTORED",
            )
        ).all()
        restored_lot_qty = {(a.purchase_lot_id, a.allocated_quantity) for a in restored}
        assert restored_lot_qty == {(lot_a.id, Decimal("6")), (lot_b.id, Decimal("4"))}
        unresolved = check.scalars(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == return_movement.id,
                FifoAllocation.purchase_lot_id.is_(None),
            )
        ).all()
        assert unresolved == []
    finally:
        check.close()


def test_damaged_return_recorded_as_loss_not_restocked(packet2b_env):
    session = packet2b_env["session"]
    branch = packet2b_env["branch"]
    item = packet2b_env["item"]
    cashier = packet2b_env["cashier"]
    now = datetime.now(timezone.utc)
    _, line = _create_purchase_line(session, branch, item, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), date(2024, 1, 1))
    lot = _engine_lot(session, branch, item, line, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), now)
    session.commit()

    sale, sale_line, _ = _sell_from_lots(session, branch, item, cashier, now, [(lot, Decimal("10"))])
    result = _complete_return(session, branch, cashier, sale, [ReturnLineInput(sale_line.id, Decimal("3"), "DAMAGED")], now)
    session.commit()

    check = _fresh(packet2b_env)
    try:
        loss = check.scalar(
            select(DamageLossRecord).where(
                DamageLossRecord.source_type == "RETURN",
                DamageLossRecord.source_id == result.return_id,
            )
        )
        assert loss is not None
        assert loss.quantity == Decimal("3")
        assert loss.review_status == "APPROVED"
        assert loss.approved_by == cashier.id

        assert check.get(PurchaseLot, lot.id).remaining_quantity == Decimal("0"), "damaged return must not restock the lot"
        restored = check.scalars(
            select(FifoAllocation).join(StockMovement, StockMovement.id == FifoAllocation.stock_movement_id).where(
                StockMovement.source_type.in_(["RETURN", "DAMAGE_RETURN"]),
                StockMovement.source_id == result.return_id,
            )
        ).all()
        assert restored == []
    finally:
        check.close()


def test_good_repair_part_return_restores_original_fifo_lineage(packet2b_env):
    session = packet2b_env["session"]
    branch = packet2b_env["branch"]
    item = packet2b_env["item"]
    cashier = packet2b_env["cashier"]
    now = datetime.now(timezone.utc)
    _, line = _create_purchase_line(session, branch, item, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), date(2024, 1, 1))
    lot = _engine_lot(session, branch, item, line, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), now)
    session.commit()

    repair = _create_repair(session, branch, cashier, now)
    part = _add_repair_part(session, branch, cashier, repair, item, Decimal("3"))
    assert part.status == "USED"
    assert lot.remaining_quantity == Decimal("7")

    # stock_movement_id must reference the real consumption movement created by
    # FifoEngine.consume (RepairService.add_part now stores allocation.movement_id).
    movement = session.get(StockMovement, part.stock_movement_id)
    assert movement is not None
    assert movement.source_type == "REPAIR_PART"

    service = RepairService(session)
    service.remove_part(repair.id, part.id, branch.id, cashier.id, condition="GOOD", reason="No longer needed")
    session.commit()

    check = _fresh(packet2b_env)
    try:
        assert check.get(PurchaseLot, lot.id).remaining_quantity == Decimal("10"), "good returned part must restore the lot to its original quantity"
        assert check.get(type(part), part.id).status == "RETURNED"
        reverse = check.scalar(
            select(StockMovement).where(
                StockMovement.source_type == "REPAIR_PART_RETURN",
                StockMovement.source_id == repair.id,
            )
        )
        assert reverse is not None
        restored = check.scalars(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == reverse.id,
                FifoAllocation.allocation_status == "REPAIR_RETURN",
            )
        ).all()
        assert [(a.purchase_lot_id, a.allocated_quantity, a.allocated_unit_cost) for a in restored] == [
            (lot.id, Decimal("3"), Decimal("100.00"))
        ]
    finally:
        check.close()


def test_damaged_repair_part_follows_review_approval_workflow(packet2b_env):
    session = packet2b_env["session"]
    branch = packet2b_env["branch"]
    item = packet2b_env["item"]
    cashier = packet2b_env["cashier"]
    admin = packet2b_env["admin"]
    now = datetime.now(timezone.utc)
    _, line = _create_purchase_line(session, branch, item, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), date(2024, 1, 1))
    lot = _engine_lot(session, branch, item, line, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), now)
    session.commit()

    repair = _create_repair(session, branch, cashier, now)
    part1 = _add_repair_part(session, branch, cashier, repair, item, Decimal("3"))
    part2 = _add_repair_part(session, branch, cashier, repair, item, Decimal("2"))
    assert part1.status == "USED"
    assert part2.status == "USED"

    service = RepairService(session)
    service.remove_part(repair.id, part1.id, branch.id, cashier.id, condition="DAMAGED", reason="Cracked on receipt")
    session.commit()

    check = _fresh(packet2b_env)
    try:
        loss1 = check.scalar(
            select(DamageLossRecord).where(
                DamageLossRecord.source_type == "REPAIR_PART_REMOVAL",
                DamageLossRecord.source_id == part1.id,
            )
        )
        assert loss1 is not None
        assert loss1.quantity == Decimal("3")
        assert loss1.review_status == "PENDING_ADMIN"
        assert loss1.approved_by is None

        assert check.get(type(part1), part1.id).status == "DAMAGED_REVIEW"

        review1 = service.review_damaged_part(part1.id, branch.id, admin.id, approve_loss=True, reason="Approved", version=loss1.version)
        assert review1["review_status"] == "APPROVED"
        assert review1["status"] == "DAMAGED"
        session.commit()
        check2 = _fresh(packet2b_env)
        try:
            assert check2.get(DamageLossRecord, loss1.id).review_status == "APPROVED"
        finally:
            check2.close()

        service.remove_part(repair.id, part2.id, branch.id, cashier.id, condition="DAMAGED", reason="Also cracked")
        session.commit()
        loss2 = check.scalar(
            select(DamageLossRecord).where(
                DamageLossRecord.source_type == "REPAIR_PART_REMOVAL",
                DamageLossRecord.source_id == part2.id,
            )
        )
        review2 = service.review_damaged_part(part2.id, branch.id, admin.id, approve_loss=False, reason="Rejected", version=loss2.version)
        assert review2["review_status"] == "REJECTED"
        assert review2["status"] == "USED"
        session.commit()
        check3 = _fresh(packet2b_env)
        try:
            assert check3.get(DamageLossRecord, loss2.id).review_status == "REJECTED"
        finally:
            check3.close()
    finally:
        check.close()


def test_purchase_cost_correction_recalculates_dependent_costs_preserves_lineage(packet2b_env):
    session = packet2b_env["session"]
    branch = packet2b_env["branch"]
    item = packet2b_env["item"]
    admin = packet2b_env["admin"]
    now = datetime.now(timezone.utc)
    _, line = _create_purchase_line(session, branch, item, Decimal("5"), None, date(2024, 1, 1), date(2024, 1, 1))
    lot = PurchaseLot(
        branch_id=branch.id,
        purchase_line_id=line.id,
        item_id=item.id,
        original_quantity=Decimal("5"),
        remaining_quantity=Decimal("5"),
        unit_cost=Decimal("100.00"),
        lot_date=date(2024, 1, 1),
        is_closed=False,
    )
    session.add(lot)
    session.flush()

    sale, sale_line, movement = _sell_from_lots(session, branch, item, cashier := packet2b_env["cashier"], now, [(lot, Decimal("3"))])
    sale.total_cost = Decimal("300.00")
    session.add(sale)
    session.commit()

    service = PurchaseCorrectionService(session)
    old, corrected_lot, recalc = service.change_cost(
        purchase_line=line, new_cost=Decimal("120.00"), reason="Supplier invoice correction", actor_user_id=admin.id
    )
    session.commit()

    assert old == Decimal("100.00")
    assert corrected_lot.unit_cost == Decimal("120.00")
    assert recalc["sale_count"] == 1

    check = _fresh(packet2b_env)
    try:
        alloc = check.scalar(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == movement.id,
                FifoAllocation.purchase_lot_id == lot.id,
            )
        )
        assert alloc is not None
        assert alloc.allocated_unit_cost == Decimal("120.00")
        assert alloc.allocated_quantity == Decimal("3")
        assert alloc.allocation_status == "ALLOCATED"
        assert check.get(Sale, sale.id).total_cost == Decimal("360.00"), "sale total must reflect repriced allocation"
        assert check.get(PurchaseLot, lot.id).unit_cost == Decimal("120.00")
    finally:
        check.close()


def test_purchase_quantity_increase_reconciles_negative_stock_consistently(packet2b_env):
    session = packet2b_env["session"]
    branch = packet2b_env["branch"]
    item = packet2b_env["item"]
    admin = packet2b_env["admin"]
    now = datetime.now(timezone.utc)
    _, line = _create_purchase_line(session, branch, item, Decimal("5"), Decimal("100.00"), date(2024, 1, 1), date(2024, 1, 1))
    lot = PurchaseLot(
        branch_id=branch.id,
        purchase_line_id=line.id,
        item_id=item.id,
        original_quantity=Decimal("5"),
        remaining_quantity=Decimal("5"),
        unit_cost=Decimal("100.00"),
        lot_date=date(2024, 1, 1),
        is_closed=False,
    )
    session.add(lot)
    session.flush()

    sale, sale_line, movement = _sell_from_lots(
        session, branch, item, packet2b_env["cashier"], now, [(lot, Decimal("5"))]
    )
    session.add(
        FifoAllocation(
            stock_movement_id=movement.id,
            purchase_lot_id=None,
            allocated_quantity=Decimal("2"),
            allocated_unit_cost=None,
            allocation_status="NEGATIVE_STOCK",
            created_at=now,
        )
    )
    lot.remaining_quantity = Decimal("0")
    lot.is_closed = True
    session.commit()

    service = PurchaseCorrectionService(session)
    old, new_qty, corrected_lot = service.change_quantity(
        purchase_line=line, new_quantity=Decimal("8"), reason="Received more units than booked", actor_user_id=admin.id
    )
    session.commit()

    assert old == Decimal("5")
    assert new_qty == Decimal("8")
    assert corrected_lot.original_quantity == Decimal("8")
    assert corrected_lot.remaining_quantity == Decimal("1")

    check = _fresh(packet2b_env)
    try:
        negatives = check.scalars(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == movement.id,
                FifoAllocation.allocation_status == "NEGATIVE_STOCK",
            )
        ).all()
        assert negatives == []
        reconciled = check.scalars(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == movement.id,
                FifoAllocation.allocation_status == "RECONCILED",
            )
        ).all()
        assert [(a.purchase_lot_id, a.allocated_quantity, a.allocated_unit_cost) for a in reconciled] == [
            (lot.id, Decimal("2"), Decimal("100.00"))
        ]
    finally:
        check.close()


def test_purchase_quantity_decrease_when_stock_already_sold_reduces_remaining(packet2b_env):
    session = packet2b_env["session"]
    branch = packet2b_env["branch"]
    item = packet2b_env["item"]
    cashier = packet2b_env["cashier"]
    admin = packet2b_env["admin"]
    now = datetime.now(timezone.utc)
    _, line = _create_purchase_line(session, branch, item, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), date(2024, 1, 1))
    lot = _engine_lot(session, branch, item, line, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), now)
    session.commit()

    # 6 of 10 units already sold/consumed -> remaining = 4
    sale, sale_line, movement = _sell_from_lots(session, branch, item, cashier, now, [(lot, Decimal("6"))])
    assert lot.remaining_quantity == Decimal("4")
    assert movement.quantity_delta == Decimal("-6")

    service = PurchaseCorrectionService(session)
    old, new_qty, corrected_lot = service.change_quantity(
        purchase_line=line, new_quantity=Decimal("8"), reason="Received fewer units than booked", actor_user_id=admin.id
    )
    session.commit()

    assert old == Decimal("10")
    assert new_qty == Decimal("8")
    assert corrected_lot.original_quantity == Decimal("8")
    assert corrected_lot.remaining_quantity == Decimal("2"), "remaining must drop by the reduction only, not below consumed"
    assert corrected_lot.is_closed is False

    check = _fresh(packet2b_env)
    try:
        assert check.get(PurchaseLine, line.id).quantity == Decimal("8")
        assert check.get(PurchaseLot, lot.id).remaining_quantity == Decimal("2")
        assert check.get(PurchaseLot, lot.id).unit_cost == Decimal("100.00")
        correction_movement = check.scalar(
            select(StockMovement).where(
                StockMovement.source_type == "PURCHASE_CORRECTION", StockMovement.source_id == line.id
            )
        )
        assert correction_movement is not None
        assert correction_movement.quantity_delta == Decimal("-2")
        alloc = check.scalar(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == correction_movement.id,
                FifoAllocation.purchase_lot_id == lot.id,
                FifoAllocation.allocation_status == "PURCHASE_QUANTITY_CORRECTION",
            )
        )
        assert alloc is not None
        assert alloc.allocated_quantity == Decimal("2")
        assert alloc.allocated_unit_cost == Decimal("100.00")
    finally:
        check.close()


def test_purchase_quantity_decrease_below_consumed_is_rejected_with_state_unchanged(packet2b_env):
    session = packet2b_env["session"]
    branch = packet2b_env["branch"]
    item = packet2b_env["item"]
    cashier = packet2b_env["cashier"]
    admin = packet2b_env["admin"]
    now = datetime.now(timezone.utc)
    _, line = _create_purchase_line(session, branch, item, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), date(2024, 1, 1))
    lot = _engine_lot(session, branch, item, line, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), now)
    session.commit()

    # 6 of 10 units already sold/consumed -> remaining = 4, consumed = 6
    sale, sale_line, movement = _sell_from_lots(session, branch, item, cashier, now, [(lot, Decimal("6"))])
    assert lot.remaining_quantity == Decimal("4")

    sale_allocation_id = session.scalar(
        select(FifoAllocation.id).where(
            FifoAllocation.stock_movement_id == movement.id,
            FifoAllocation.purchase_lot_id == lot.id,
            FifoAllocation.allocation_status == "ALLOCATED",
        )
    )
    assert sale_allocation_id is not None

    service = PurchaseCorrectionService(session)
    with pytest.raises(
        PurchaseCorrectionError,
        match="Quantity cannot be reduced below quantity already consumed by FIFO",
    ):
        service.change_quantity(
            purchase_line=line, new_quantity=Decimal("5"), reason="Booked more than actually received", actor_user_id=admin.id
        )

    check = _fresh(packet2b_env)
    try:
        assert check.get(PurchaseLine, line.id).quantity == Decimal("10")
        assert check.get(PurchaseLot, lot.id).original_quantity == Decimal("10")
        assert check.get(PurchaseLot, lot.id).remaining_quantity == Decimal("4")
        assert check.get(PurchaseLot, lot.id).is_closed is False
        alloc = check.get(FifoAllocation, sale_allocation_id)
        assert alloc is not None
        assert alloc.allocated_quantity == Decimal("6")
        assert alloc.allocation_status == "ALLOCATED"
        assert check.scalars(select(FifoAllocation).where(FifoAllocation.stock_movement_id == movement.id)).all() == [alloc]
        corrections = check.scalars(
            select(StockMovement).where(
                StockMovement.source_type == "PURCHASE_CORRECTION", StockMovement.source_id == line.id
            )
        ).all()
        assert corrections == []
    finally:
        check.close()


def test_purchase_date_correction_replay_supported_with_purchase_only_lineage(packet2b_env):
    session = packet2b_env["session"]
    branch = packet2b_env["branch"]
    item = packet2b_env["item"]
    admin = packet2b_env["admin"]
    now = datetime.now(timezone.utc)
    _, line_a = _create_purchase_line(session, branch, item, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), date(2024, 1, 1))
    lot_a = PurchaseLot(
        branch_id=branch.id,
        purchase_line_id=line_a.id,
        item_id=item.id,
        original_quantity=Decimal("5"),
        remaining_quantity=Decimal("5"),
        unit_cost=Decimal("100.00"),
        lot_date=date(2024, 1, 1),
        is_closed=False,
    )
    session.add(lot_a)
    session.add(
        StockMovement(
            branch_id=branch.id,
            item_id=item.id,
            source_type="PURCHASE",
            source_id=line_a.id,
            quantity_delta=Decimal("5"),
            occurred_at=now,
        )
    )
    line_b = PurchaseLine(
        purchase_id=line_a.purchase_id,
        item_id=item.id,
        quantity=Decimal("5"),
        unit_cost=Decimal("200.00"),
        line_date=date(2024, 1, 10),
    )
    session.add(line_b)
    session.flush()
    lot_b = PurchaseLot(
        branch_id=branch.id,
        purchase_line_id=line_b.id,
        item_id=item.id,
        original_quantity=Decimal("5"),
        remaining_quantity=Decimal("5"),
        unit_cost=Decimal("200.00"),
        lot_date=date(2024, 1, 10),
        is_closed=False,
    )
    session.add(lot_b)
    session.add(
        StockMovement(
            branch_id=branch.id,
            item_id=item.id,
            source_type="PURCHASE",
            source_id=line_b.id,
            quantity_delta=Decimal("5"),
            occurred_at=now,
        )
    )
    session.commit()

    sale, sale_line, movement = _sell_from_lots(
        session, branch, item, packet2b_env["cashier"],
        datetime(2024, 1, 5, 12, 0, tzinfo=timezone.utc),
        [(lot_a, Decimal("3"))],
    )
    session.commit()

    service = PurchaseCorrectionService(session)
    old_date, corrected_lot = service.change_date(
        purchase_line=line_a, new_date=date(2024, 1, 20), reason="Lot date was miskeyed", actor_user_id=admin.id
    )
    session.commit()

    assert old_date == date(2024, 1, 1)
    assert corrected_lot.lot_date == date(2024, 1, 20)

    check = _fresh(packet2b_env)
    try:
        assert check.get(PurchaseLot, lot_a.id).lot_date == date(2024, 1, 20)
        assert check.get(PurchaseLot, lot_a.id).remaining_quantity == Decimal("5")
        assert check.get(PurchaseLot, lot_b.id).remaining_quantity == Decimal("5")
        remaining_allocs = check.scalars(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == movement.id,
                FifoAllocation.allocation_status == "ALLOCATED",
            )
        ).all()
        assert remaining_allocs == []
        unresolved = check.scalars(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == movement.id,
                FifoAllocation.allocation_status == "NEGATIVE_STOCK",
            )
        ).all()
        assert [a.allocated_quantity for a in unresolved] == [Decimal("3")]
    finally:
        check.close()


def test_purchase_date_correction_blocked_with_non_purchase_positive_lineage(packet2b_env):
    session = packet2b_env["session"]
    branch = packet2b_env["branch"]
    item = packet2b_env["item"]
    admin = packet2b_env["admin"]
    now = datetime.now(timezone.utc)
    _, line_a = _create_purchase_line(session, branch, item, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), date(2024, 1, 1))
    lot_a = PurchaseLot(
        branch_id=branch.id,
        purchase_line_id=line_a.id,
        item_id=item.id,
        original_quantity=Decimal("5"),
        remaining_quantity=Decimal("5"),
        unit_cost=Decimal("100.00"),
        lot_date=date(2024, 1, 1),
        is_closed=False,
    )
    session.add(lot_a)
    session.add(
        StockMovement(
            branch_id=branch.id,
            item_id=item.id,
            source_type="PURCHASE",
            source_id=line_a.id,
            quantity_delta=Decimal("5"),
            occurred_at=now,
        )
    )
    sale, sale_line, movement = _sell_from_lots(
        session, branch, item, packet2b_env["cashier"],
        datetime(2024, 1, 5, 12, 0, tzinfo=timezone.utc),
        [(lot_a, Decimal("3"))],
    )
    session.add(
        StockMovement(
            branch_id=branch.id,
            item_id=item.id,
            source_type="RETURN",
            source_id=uuid.uuid4(),
            quantity_delta=Decimal("1"),
            occurred_at=now,
        )
    )
    session.commit()

    service = PurchaseCorrectionService(session)
    with pytest.raises(PurchaseCorrectionError, match="blocked"):
        service.change_date(
            purchase_line=line_a, new_date=date(2024, 1, 20), reason="Should not replay", actor_user_id=admin.id
        )
    session.commit()

    check = _fresh(packet2b_env)
    try:
        assert check.get(PurchaseLot, lot_a.id).lot_date == date(2024, 1, 1)
    finally:
        check.close()


def test_repair_service_rejects_invalid_transition(packet2b_env):
    session = packet2b_env["session"]
    branch = packet2b_env["branch"]
    cashier = packet2b_env["cashier"]
    now = datetime.now(timezone.utc)
    repair = _create_repair(session, branch, cashier, now)
    service = RepairService(session)
    with pytest.raises(RepairValidationError, match="Invalid repair status transition"):
        service.set_status(repair.id, branch.id, cashier.id, "READY")


def test_repair_part_stock_movement_id_references_consumption_movement(packet2b_env):
    session = packet2b_env["session"]
    branch = packet2b_env["branch"]
    item = packet2b_env["item"]
    cashier = packet2b_env["cashier"]
    now = datetime.now(timezone.utc)
    _, line = _create_purchase_line(session, branch, item, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), date(2024, 1, 1))
    lot = _engine_lot(session, branch, item, line, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), now)
    session.commit()

    repair = _create_repair(session, branch, cashier, now)
    part = _add_repair_part(session, branch, cashier, repair, item, Decimal("3"))
    assert part.status == "USED"
    assert lot.remaining_quantity == Decimal("7")

    # stock_movement_id must reference the actual consumption movement, not the
    # source_id passed to FifoEngine.consume (consume generates its own movement id).
    movement = session.get(StockMovement, part.stock_movement_id)
    assert movement is not None, "RepairPart.stock_movement_id does not reference a real StockMovement"
    assert movement.source_type == "REPAIR_PART"
    assert movement.quantity_delta == Decimal("-3")

    service = RepairService(session)
    service.remove_part(repair.id, part.id, branch.id, cashier.id, condition="GOOD", reason="No longer needed")
    session.commit()

    check = _fresh(packet2b_env)
    try:
        assert check.get(PurchaseLot, lot.id).remaining_quantity == Decimal("10"), "good returned part must restore the lot to its original quantity"
        assert check.get(type(part), part.id).status == "RETURNED"
        reverse = check.scalar(
            select(StockMovement).where(
                StockMovement.source_type == "REPAIR_PART_RETURN",
                StockMovement.source_id == repair.id,
            )
        )
        assert reverse is not None
        restored = check.scalars(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == reverse.id,
                FifoAllocation.allocation_status == "REPAIR_RETURN",
            )
        ).all()
        assert [(a.purchase_lot_id, a.allocated_quantity, a.allocated_unit_cost) for a in restored] == [
            (lot.id, Decimal("3"), Decimal("100.00"))
        ]
    finally:
        check.close()


def test_purchase_cost_correction_updates_sale_total_cost(packet2b_env):
    session = packet2b_env["session"]
    branch = packet2b_env["branch"]
    item = packet2b_env["item"]
    cashier = packet2b_env["cashier"]
    admin = packet2b_env["admin"]
    now = datetime.now(timezone.utc)
    _, line = _create_purchase_line(session, branch, item, Decimal("5"), None, date(2024, 1, 1), date(2024, 1, 1))
    lot = PurchaseLot(
        branch_id=branch.id,
        purchase_line_id=line.id,
        item_id=item.id,
        original_quantity=Decimal("5"),
        remaining_quantity=Decimal("5"),
        unit_cost=Decimal("100.00"),
        lot_date=date(2024, 1, 1),
        is_closed=False,
    )
    session.add(lot)
    session.flush()

    sale, sale_line, movement = _sell_from_lots(session, branch, item, cashier, now, [(lot, Decimal("3"))])
    sale.total_cost = Decimal("300.00")
    session.add(sale)
    session.commit()

    service = PurchaseCorrectionService(session)
    old, corrected_lot, recalc = service.change_cost(
        purchase_line=line, new_cost=Decimal("120.00"), reason="Supplier invoice correction", actor_user_id=admin.id
    )
    session.commit()

    assert old == Decimal("100.00")
    assert corrected_lot.unit_cost == Decimal("120.00")
    assert recalc["sale_count"] == 1

    check = _fresh(packet2b_env)
    try:
        alloc = check.scalar(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == movement.id,
                FifoAllocation.purchase_lot_id == lot.id,
            )
        )
        assert alloc is not None
        assert alloc.allocated_unit_cost == Decimal("120.00")
        assert alloc.allocated_quantity == Decimal("3")
        assert alloc.allocation_status == "ALLOCATED"
        assert check.get(Sale, sale.id).total_cost == Decimal("360.00"), "sale total must reflect repriced allocation"
        assert check.get(PurchaseLot, lot.id).unit_cost == Decimal("120.00")
    finally:
        check.close()


def test_purchase_cost_correction_repeat_does_not_double_apply(packet2b_env):
    session = packet2b_env["session"]
    branch = packet2b_env["branch"]
    item = packet2b_env["item"]
    cashier = packet2b_env["cashier"]
    admin = packet2b_env["admin"]
    now = datetime.now(timezone.utc)
    _, line = _create_purchase_line(session, branch, item, Decimal("5"), None, date(2024, 1, 1), date(2024, 1, 1))
    lot = PurchaseLot(
        branch_id=branch.id,
        purchase_line_id=line.id,
        item_id=item.id,
        original_quantity=Decimal("5"),
        remaining_quantity=Decimal("5"),
        unit_cost=Decimal("100.00"),
        lot_date=date(2024, 1, 1),
        is_closed=False,
    )
    session.add(lot)
    session.flush()

    sale, sale_line, movement = _sell_from_lots(session, branch, item, cashier, now, [(lot, Decimal("3"))])
    sale.total_cost = Decimal("300.00")
    session.add(sale)
    session.commit()

    service = PurchaseCorrectionService(session)
    service.change_cost(purchase_line=line, new_cost=Decimal("120.00"), reason="First correction", actor_user_id=admin.id)
    session.commit()
    assert check_get_sale_total(session, sale.id) == Decimal("360.00")

    service.change_cost(purchase_line=line, new_cost=Decimal("100.00"), reason="Revert correction", actor_user_id=admin.id)
    session.commit()
    assert check_get_sale_total(session, sale.id) == Decimal("300.00"), "reverting the correction must restore the original total"

    check = _fresh(packet2b_env)
    try:
        allocs = check.scalars(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == movement.id,
                FifoAllocation.purchase_lot_id == lot.id,
            )
        ).all()
        assert len(allocs) == 1, "repeating the correction must not duplicate allocations"
        assert allocs[0].allocated_unit_cost == Decimal("100.00")
        assert check.get(Sale, sale.id).total_cost == Decimal("300.00")
    finally:
        check.close()


def check_get_sale_total(session, sale_id):
    return session.scalar(select(Sale.total_cost).where(Sale.id == sale_id))


def test_good_return_idempotent_replay_does_not_restore_stock_twice(packet2b_env):
    session = packet2b_env["session"]
    branch = packet2b_env["branch"]
    item = packet2b_env["item"]
    cashier = packet2b_env["cashier"]
    now = datetime.now(timezone.utc)
    _, line = _create_purchase_line(session, branch, item, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), date(2024, 1, 1))
    lot = _engine_lot(session, branch, item, line, Decimal("10"), Decimal("100.00"), date(2024, 1, 1), now)
    session.commit()

    sale, sale_line, _ = _sell_from_lots(session, branch, item, cashier, now, [(lot, Decimal("10"))])
    assert lot.remaining_quantity == Decimal("0")

    key = "idem-return-good-1"
    return_lines = [ReturnLineInput(sale_line.id, Decimal("6"), "GOOD")]

    def build_request():
        return ReturnRequest(
            branch_id=branch.id,
            cashier_id=cashier.id,
            original_sale_id=sale.id,
            lines=tuple(return_lines),
            return_datetime=now,
            idempotency_key=key,
        )

    service = ReturnService(session)
    result1 = service.complete(build_request())
    session.commit()

    check = _fresh(packet2b_env)
    try:
        assert check.get(PurchaseLot, lot.id).remaining_quantity == Decimal("6"), "first return must restore only the returned quantity"
        movement = check.scalar(
            select(StockMovement).where(
                StockMovement.source_type == "RETURN", StockMovement.source_id == result1.return_id
            )
        )
        assert movement is not None
        restored = check.scalars(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == movement.id,
                FifoAllocation.allocation_status == "RETURN_RESTORED",
            )
        ).all()
        assert [(a.purchase_lot_id, a.allocated_quantity) for a in restored] == [(lot.id, Decimal("6"))]
        assert check.scalar(select(func.count(Return.id)).where(Return.original_sale_id == sale.id)) == 1
        assert check.get(Return, result1.return_id).status == "COMPLETED"
    finally:
        check.close()

    result2 = service.complete(build_request())
    session.commit()

    check2 = _fresh(packet2b_env)
    try:
        assert result2.return_id == result1.return_id, "idempotent replay must return the original return record"
        assert result2.return_no == result1.return_no
        assert result2.refund_total == result1.refund_total

        assert check2.get(PurchaseLot, lot.id).remaining_quantity == Decimal("6"), "idempotent replay must not restore FIFO stock more than once"

        movements = check2.scalars(
            select(StockMovement).where(
                StockMovement.source_type == "RETURN", StockMovement.source_id == result1.return_id
            )
        ).all()
        assert len(movements) == 1, "idempotent replay must not create a second RETURN stock movement"

        restored2 = check2.scalars(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == movements[0].id,
                FifoAllocation.allocation_status == "RETURN_RESTORED",
            )
        ).all()
        assert [(a.purchase_lot_id, a.allocated_quantity) for a in restored2] == [(lot.id, Decimal("6"))], "idempotent replay must not duplicate RETURN_RESTORED FIFO lineage"

        assert check2.scalar(select(func.count(Return.id)).where(Return.original_sale_id == sale.id)) == 1, "idempotent replay must not create a second return record"
        ret = check2.get(Return, result1.return_id)
        assert ret.status == "COMPLETED"
        assert ret.return_no == result1.return_no
        assert ret.refund_total == result1.refund_total

        idem = check2.scalar(select(IdempotencyKey).where(IdempotencyKey.key == key))
        assert idem is not None
        assert idem.completed_at is not None
        assert idem.response_json is not None
        assert idem.request_hash == ReturnService.canonical_request_hash(build_request())
    finally:
        check2.close()
