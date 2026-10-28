"""Stock adjustment / damage-loss on IMEI-tracked phones must name the phones, and those phones leave IN_STOCK
(otherwise a phone counted as gone could still be sold)."""
import uuid

import pytest

from tests.test_e2e_requirements import PASSWORD_ADMIN, _db_available, _ensure_day, ctx  # noqa: F401
from tests.test_e2e_serialized import _buy, _imei, _units, phone  # noqa: F401

pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")
PW = {"admin_password": PASSWORD_ADMIN}


def _stock(ctx, item):
    return float(next(x["stock"] for x in ctx["c"].get("/api/v1/inventory/summary", headers=ctx["A"]).json() if x["item_id"] == item["item_id"]))


def _post(ctx, path, body):
    return ctx["c"].post(path, params=PW, headers=ctx["A"], json={**body, "idempotency_key": uuid.uuid4().hex})


def test_damage_loss_of_a_phone_needs_its_imei_and_blocks_selling_it(ctx, phone):
    a, b = _imei(), _imei()
    assert _buy(ctx, phone, [a, b]).status_code == 200
    ua, ub = (_units(ctx, phone, q=x)[0] for x in (a, b))
    before = _stock(ctx, phone)

    no_imei = _post(ctx, "/api/v1/stock-control/damage-loss", {"item_id": phone["item_id"], "quantity": "1", "reason": "dropped"})
    assert no_imei.status_code == 400 and "IMEI" in no_imei.text and _stock(ctx, phone) == before

    ok = _post(ctx, "/api/v1/stock-control/damage-loss", {"item_id": phone["item_id"], "quantity": "1", "reason": "dropped", "serialized_unit_ids": [ua["serialized_unit_id"]]})
    assert ok.status_code == 200, ok.text
    assert _stock(ctx, phone) == before - 1
    assert _units(ctx, phone, q=a)[0]["status"] == "DAMAGED" and _units(ctx, phone, q=b)[0]["status"] == "IN_STOCK"

    _ensure_day(ctx)  # the written-off phone can no longer be sold
    sale = ctx["c"].post("/api/v1/sales", headers=ctx["C"], json={
        "lines": [{"item_id": phone["item_id"], "quantity": "1", "unit_price": "1000", "serialized_unit_id": ua["serialized_unit_id"]}],
        "payments": [{"method": "CASH", "amount": "1000"}], "idempotency_key": uuid.uuid4().hex})
    assert sale.status_code == 400
    again = _post(ctx, "/api/v1/stock-control/damage-loss", {"item_id": phone["item_id"], "quantity": "1", "reason": "x", "serialized_unit_ids": [ua["serialized_unit_id"]]})
    assert again.status_code == 400 and "IN_STOCK" in again.text


def test_stock_adjustment_for_phones_goes_through_imeis_only(ctx, phone):
    c = _imei()
    assert _buy(ctx, phone, [c]).status_code == 200
    up = _post(ctx, "/api/v1/stock-control/adjust", {"item_id": phone["item_id"], "quantity_delta": "1", "reason": "found"})
    assert up.status_code == 400 and "Purchases" in up.text
    down_plain = _post(ctx, "/api/v1/stock-control/adjust", {"item_id": phone["item_id"], "quantity_delta": "-1", "reason": "lost"})
    assert down_plain.status_code == 400
    uc = _units(ctx, phone, q=c)[0]
    down = _post(ctx, "/api/v1/stock-control/adjust", {"item_id": phone["item_id"], "quantity_delta": "-1", "reason": "lost", "serialized_unit_ids": [uc["serialized_unit_id"]]})
    assert down.status_code == 200, down.text
    assert _units(ctx, phone, q=c)[0]["status"] == "WRITTEN_OFF"


def test_plain_items_are_unaffected(ctx):
    from tests.test_e2e_requirements import _new_item, _purchase
    item = _new_item(ctx)
    _purchase(ctx, item["item_id"], 5, 100)
    r = _post(ctx, "/api/v1/stock-control/damage-loss", {"item_id": item["item_id"], "quantity": "1", "reason": "broken"})
    assert r.status_code == 200, r.text
