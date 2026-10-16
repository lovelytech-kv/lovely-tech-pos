"""PostgreSQL-only isolated concurrency tests for FIFO lot handling.

These tests require a dedicated disposable PostgreSQL database already provisioned
with the application schema (via Alembic, run by an administrator separately).
No DDL, migrations, or schema creation are performed by this module. Disposable
database must be reset by an administrator before rerunning these tests; no
unrelated records are deleted here.
"""

import os
import re
import threading
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

_SYSTEM_DATABASES = frozenset({"postgres", "template0", "template1"})
_DISPOSABLE_DB_PATTERN = re.compile(r"^(test_|.*_test_|.*_test$)")
_VALID_SCHEMES = frozenset({"postgresql", "postgresql+psycopg", "postgresql+psycopg2"})


def _validate_test_database_url(url: str) -> tuple[bool, str]:
    try:
        parsed = urlparse(url)
    except Exception as exc:  # pragma: no cover
        return False, f"invalid URL format: {exc}"
    if parsed.scheme not in _VALID_SCHEMES:
        return False, f"unsupported scheme '{parsed.scheme}'; 'postgres' scheme is rejected"
    db_name = parsed.path.lstrip("/")
    if not db_name:
        return False, "database name missing from URL path"
    if db_name in _SYSTEM_DATABASES:
        return False, f"database '{db_name}' is a protected system database"
    if not _DISPOSABLE_DB_PATTERN.match(db_name):
        return False, f"database name '{db_name}' does not match disposable test pattern"
    return True, "ok"


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    pytest.skip("TEST_DATABASE_URL not set; skipping PostgreSQL FIFO concurrency tests", allow_module_level=True)

_valid, _reason = _validate_test_database_url(TEST_DATABASE_URL)
if not _valid:
    pytest.fail(f"TEST_DATABASE_URL validation failed: {_reason}", pytrace=False)

# Never reuse app cached engine; build a fresh NullPool engine from the test URL only.
def _engine():
    return create_engine(TEST_DATABASE_URL, poolclass=NullPool)


# Do NOT import migration test modules or settings.database_url.
from app.fifo.engine import FifoEngine
from app.models.inventory import FifoAllocation, PurchaseLot, Purchase, PurchaseLine, Item, Branch, StockMovement


def _seed_branch_item(session: Session):
    branch_id = uuid.uuid4()
    item_id = uuid.uuid4()
    session.execute(text("INSERT INTO branches (id, code, name, created_at, updated_at) VALUES (:id,'T','Test',now(),now())"), {"id": branch_id})
    session.execute(text("INSERT INTO items (id, branch_id, sku, name, created_at, updated_at) VALUES (:id,:b,'SKU','Item',now(),now())"), {"id": item_id, "b": branch_id})
    session.commit()
    return branch_id, item_id


def test_concurrent_fifo_lot_consumption_conserves_quantity():
    """Two threads consume the same lot; total consumed must not exceed original."""
    engine = _engine()
    branch_id, item_id = None, None
    with Session(engine) as s:
        branch_id, item_id = _seed_branch_item(s)

    # Create a lot with quantity 10
    lot_qty = Decimal("10")
    with Session(engine) as s:
        # create purchase + line
        pur_id = uuid.uuid4()
        s.execute(text("INSERT INTO purchases (id, branch_id, reference_no, purchase_date, status, payment_method, version, created_at, updated_at) VALUES (:id,:b,'R',CURRENT_DATE,'PENDING_COST','CASH',1,now(),now())"), {"id": pur_id, "b": branch_id})
        line_id = uuid.uuid4()
        s.execute(text("INSERT INTO purchase_lines (id, purchase_id, item_id, quantity, unit_cost, line_date, version, created_at, updated_at) VALUES (:id,:p,:i,10,1.0,'2026-01-01',1,now(),now())"), {"id": line_id, "p": pur_id, "i": item_id})
        s.commit()
        fe = FifoEngine(s)
        fe.create_purchase_lot(branch_id=branch_id, purchase_line_id=line_id, item_id=item_id, quantity=lot_qty, unit_cost=Decimal("1.00"), lot_date=date(2026,1,1), movement_source_id=uuid.uuid4(), create_stock_movement=False)
        s.commit()

    errors = []
    barrier = threading.Barrier(2, timeout=5)

    def worker(qty):
        sess = Session(engine)
        try:
            sess.execute(text("SET LOCAL lock_timeout = '2s'"))
            barrier.wait(timeout=5)
            FifoEngine(sess).consume(branch_id=branch_id, item_id=item_id, quantity=qty, source_type="SALE", source_id=uuid.uuid4())
            sess.commit()
        except Exception as e:
            sess.rollback()
            errors.append(e)
        finally:
            sess.close()

    t1 = threading.Thread(target=worker, args=(Decimal("6"),))
    t2 = threading.Thread(target=worker, args=(Decimal("6"),))
    t1.start(); t2.start()
    t1.join(timeout=10); t2.join(timeout=10)
    if t1.is_alive() or t2.is_alive():
        raise RuntimeError("worker thread did not terminate")

    # Verify conservation in separate session
    with Session(engine) as s:
        lot = s.scalar(select(PurchaseLot).where(PurchaseLot.item_id == item_id))
        remaining = lot.remaining_quantity if lot else Decimal("0")
        consumed = lot_qty - remaining
        assert consumed <= lot_qty
        assert remaining >= Decimal("0")

        neg_allocs = s.execute(
            select(FifoAllocation, StockMovement).join(
                StockMovement, StockMovement.id == FifoAllocation.stock_movement_id
            ).where(
                FifoAllocation.allocation_status == "NEGATIVE_STOCK",
                StockMovement.branch_id == branch_id,
                StockMovement.item_id == item_id,
            )
        ).all()
        for alloc, movement in neg_allocs:
            assert alloc.allocated_quantity > Decimal("0")
            assert movement.branch_id == branch_id
            assert movement.item_id == item_id
            assert movement.quantity_delta < Decimal("0")
        total_neg = sum((a.allocated_quantity for a, _ in neg_allocs), Decimal("0"))
        assert total_neg >= Decimal("0")
    engine.dispose()


def test_negative_reconciliation_oldest_first_conserves():
    engine = _engine()
    branch_id, item_id = None, None
    source_3 = uuid.uuid4()
    source_4 = uuid.uuid4()
    with Session(engine) as s:
        branch_id, item_id = _seed_branch_item(s)

    with Session(engine) as s:
        # two unresolved negative consumptions
        FifoEngine(s).consume(branch_id=branch_id, item_id=item_id, quantity=Decimal("3"), source_type="SALE", source_id=source_3)
        FifoEngine(s).consume(branch_id=branch_id, item_id=item_id, quantity=Decimal("4"), source_type="SALE", source_id=source_4)
        s.commit()

        # partial purchase lot in separate transaction reconciles oldest first
    with Session(engine) as s:
        pur_id = uuid.uuid4()
        s.execute(text("INSERT INTO purchases (id, branch_id, reference_no, purchase_date, status, payment_method, version, created_at, updated_at) VALUES (:id,:b,'R2',CURRENT_DATE,'PENDING_COST','CASH',1,now(),now())"), {"id": pur_id, "b": branch_id})
        line_id = uuid.uuid4()
        s.execute(text("INSERT INTO purchase_lines (id, purchase_id, item_id, quantity, unit_cost, line_date, version, created_at, updated_at) VALUES (:id,:p,:i,5,2.0,'2026-01-02',1,now(),now())"), {"id": line_id, "p": pur_id, "i": item_id})
        s.commit()
        fe = FifoEngine(s)
        fe.create_purchase_lot(branch_id=branch_id, purchase_line_id=line_id, item_id=item_id, quantity=Decimal("5"), unit_cost=Decimal("2.00"), lot_date=date(2026,1,2), movement_source_id=uuid.uuid4(), create_stock_movement=False)
        s.commit()

    with Session(engine) as s:
        recon_rows = s.execute(
            select(FifoAllocation, StockMovement).join(
                StockMovement, StockMovement.id == FifoAllocation.stock_movement_id
            ).where(
                FifoAllocation.allocation_status == "RECONCILED",
                StockMovement.branch_id == branch_id,
                StockMovement.item_id == item_id,
            )
        ).all()
        total_recon = sum((a.allocated_quantity for a, _ in recon_rows), Decimal("0"))
        assert total_recon == Decimal("5")

        # oldest negative (3) is fully reconciled first
        earliest_movement_ids = [m.id for _, m in sorted(recon_rows, key=lambda r: r[1].occurred_at)]
        # ensure no remaining negative allocation for the earliest movement
        earliest_recon = min(recon_rows, key=lambda r: r[1].occurred_at)
        remaining_oldest = s.scalars(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == earliest_recon[1].id,
                FifoAllocation.allocation_status == "NEGATIVE_STOCK",
            )
        ).all()
        assert len(remaining_oldest) == 0
        assert any(a.allocated_quantity == Decimal("3") for a, m in recon_rows if m.id == earliest_recon[1].id)
    engine.dispose()
