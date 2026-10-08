from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.schemas.purchases import PurchaseCreateIn, PurchaseLineCreateIn
from app.schemas.items import ItemCreateIn, ItemUpdateIn


def test_purchase_entry_has_no_cost_field():
    item_id = uuid4()
    payload = PurchaseCreateIn(
        purchase_date=date(2026, 9, 23),
        lines=[PurchaseLineCreateIn(item_id=item_id, quantity=Decimal("2"))],
    )
    assert payload.lines[0].quantity == Decimal("2")
    assert not hasattr(payload.lines[0], "unit_cost")


def test_item_master_accepts_optional_sale_price_and_barcode():
    p = ItemCreateIn(description="USB Cable", category_id=uuid4(), item_type_id=uuid4(), master_sale_price=Decimal("750.00"), barcode="955123")
    assert p.master_sale_price == Decimal("750.00")
    assert p.barcode == "955123"


def test_item_update_requires_version_for_stale_edit_protection():
    p = ItemUpdateIn(description="USB Cable", category_id=uuid4(), item_type_id=uuid4(), version=4)
    assert p.version == 4


def test_admin_purchase_payload_accepts_optional_supplier():
    supplier_id = uuid4()
    payload = PurchaseCreateIn(
        purchase_date=date(2026, 9, 23),
        supplier_id=supplier_id,
        lines=[PurchaseLineCreateIn(item_id=uuid4(), quantity=Decimal("2"))],
    )
    assert payload.supplier_id == supplier_id
