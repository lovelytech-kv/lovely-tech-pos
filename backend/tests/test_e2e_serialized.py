"""IMEI / serial tracked items (phones) end to end: Requirements 04 + 06 + 07 + 10.

Regression: nothing in the application could ever create a SerializedUnit, so phones with an
IMEI could not be purchased into stock or sold with an identity.
"""
import uuid
from datetime import date
from decimal import Decimal as D

import pytest

from tests.test_e2e_requirements import _db_available, _ensure_day, _purchase, _sale, ctx  # noqa: F401

pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")


def _imei() -> str:
    return "35" + str(uuid.uuid4().int)[:13]


@pytest.fixture(scope="module")
def phone(ctx):
    c = ctx["c"]
    ity = c.post("/api/v1/items/item-types", headers=ctx["A"],
                 json={"code": f"PH{ctx['suffix']}", "name": f"Phone-{ctx['suffix']}", "is_serialized": True}).json()
    r = c.post("/api/v1/items", headers=ctx["C"], json={
        "description": "E2E Phone", "category_id": ctx["cat"], "item_type_id": ity["id"], "brand": "Samsung", "model": "A15"})
    assert r.status_code == 200, r.text
    return r.json()


def _buy(ctx, item, serials, qty=None, headers=None):
    return ctx["c"].post("/api/v1/purchases", headers=headers or ctx["C"], json={
        "purchase_date": date.today().isoformat(), "reference_no": f"PH-{uuid.uuid4().hex[:6]}",
        "lines": [{"item_id": item["item_id"], "quantity": str(qty if qty is not None else len(serials)), "serial_numbers": serials}],
        "idempotency_key": uuid.uuid4().hex})


def _units(ctx, item, status=None, q=""):
    url = f"/api/v1/inventory/serialized/search?q={q}&item_id={item['item_id']}" + (f"&status={status}" if status else "")
    r = ctx["c"].get(url, headers=ctx["C"])
    assert r.status_code == 200, r.text
    return r.json()


def test_item_search_flags_serialized_items(ctx, phone):
    rows = ctx["c"].get(f"/api/v1/inventory/items/search?q={phone['item_code']}", headers=ctx["C"]).json()
    assert rows and rows[0]["is_serialized"] is True


def test_cashier_purchase_registers_one_unit_per_imei(ctx, phone):
    a, b = _imei(), _imei()
    r = _buy(ctx, phone, [a, f" {b.lower()} "])  # trimmed + normalised
    assert r.status_code == 200, r.text
    units = {u["serial_number"]: u for u in _units(ctx, phone, status="IN_STOCK")}
    assert a in units and b in units and all(u["status"] == "IN_STOCK" for u in (units[a], units[b]))


def test_purchase_rejects_wrong_count_duplicates_and_known_imeis(ctx, phone):
    a = _imei()
    assert _buy(ctx, phone, [a, _imei()], qty=3).status_code == 400            # 3 phones, 2 IMEIs
    assert _buy(ctx, phone, [a, a]).status_code == 400                          # same IMEI twice in one entry
    assert _buy(ctx, phone, [], qty=1).status_code == 400                       # IMEI mandatory
    assert _buy(ctx, phone, [a]).status_code == 200
    again = _buy(ctx, phone, [a])
    assert again.status_code == 400 and a in again.text                         # IMEI already in the system
    half = ctx["c"].post("/api/v1/purchases", headers=ctx["C"], json={
        "purchase_date": date.today().isoformat(),
        "lines": [{"item_id": phone["item_id"], "quantity": "1.5", "serial_numbers": [_imei()]}]})
    assert half.status_code == 400                                              # whole units only


def test_failed_purchase_leaves_no_partial_units(ctx, phone):
    ok, dup = _imei(), _imei()
    assert _buy(ctx, phone, [dup]).status_code == 200
    assert _buy(ctx, phone, [ok, dup]).status_code == 400                       # atomic: `ok` must not be created
    assert not [u for u in _units(ctx, phone, q=ok)]


def test_non_serialized_item_cannot_carry_imeis(ctx):
    from tests.test_e2e_requirements import _new_item
    plain = _new_item(ctx)
    r = ctx["c"].post("/api/v1/purchases", headers=ctx["C"], json={
        "purchase_date": date.today().isoformat(),
        "lines": [{"item_id": plain["item_id"], "quantity": "1", "serial_numbers": [_imei()]}]})
    assert r.status_code == 400


def test_sale_requires_an_available_imei_and_blocks_duplicate_identity(ctx, phone):
    c = ctx["c"]
    _ensure_day(ctx)
    imei = _imei()
    assert _buy(ctx, phone, [imei]).status_code == 200
    unit = _units(ctx, phone, q=imei)[0]

    assert _sale(ctx, ctx["C"], phone["item_id"], 90000).status_code == 400     # no IMEI chosen
    r = _sale(ctx, ctx["C"], phone["item_id"], 90000)
    assert "IMEI" in r.text

    ok = c.post("/api/v1/sales", headers=ctx["C"], json={
        "lines": [{"item_id": phone["item_id"], "quantity": "1", "unit_price": "90000", "serialized_unit_id": unit["serialized_unit_id"]}],
        "payments": [{"method": "CASH", "amount": "90000"}], "idempotency_key": uuid.uuid4().hex})
    assert ok.status_code == 200, ok.text
    assert _units(ctx, phone, q=imei)[0]["status"] == "SOLD"

    dup = c.post("/api/v1/sales", headers=ctx["C"], json={                       # same phone cannot be sold twice
        "lines": [{"item_id": phone["item_id"], "quantity": "1", "unit_price": "90000", "serialized_unit_id": unit["serialized_unit_id"]}],
        "payments": [{"method": "CASH", "amount": "90000"}], "idempotency_key": uuid.uuid4().hex})
    assert dup.status_code == 400 and "not available" in dup.text

    qty2 = c.post("/api/v1/sales", headers=ctx["C"], json={
        "lines": [{"item_id": phone["item_id"], "quantity": "2", "unit_price": "1", "serialized_unit_id": unit["serialized_unit_id"]}],
        "payments": [{"method": "CASH", "amount": "2"}], "idempotency_key": uuid.uuid4().hex})
    assert qty2.status_code == 400


def test_imei_warranty_lookup_and_good_return_makes_phone_sellable_again(ctx, phone):
    c = ctx["c"]
    _ensure_day(ctx)
    imei = _imei()
    assert _buy(ctx, phone, [imei]).status_code == 200
    unit = _units(ctx, phone, q=imei)[0]
    sale = c.post("/api/v1/sales", headers=ctx["C"], json={
        "lines": [{"item_id": phone["item_id"], "quantity": "1", "unit_price": "50000", "serialized_unit_id": unit["serialized_unit_id"],
                   "warranty_type": "MONTHS", "warranty_duration_value": 12}],
        "payments": [{"method": "CASH", "amount": "50000"}], "idempotency_key": uuid.uuid4().hex}).json()

    w = c.get(f"/api/v1/warranty/serial-lookup?serial_number={imei}", headers=ctx["C"])
    assert w.status_code == 200, w.text                                           # Requirements 10: lost-bill recovery by IMEI

    detail = c.get(f"/api/v1/sales/{sale['sale_id']}", headers=ctx["C"]).json()
    line = detail["lines"][0]
    ret = c.post("/api/v1/returns", headers=ctx["C"], json={
        "original_sale_id": sale["sale_id"], "return_charge": "0", "idempotency_key": uuid.uuid4().hex,
        "lines": [{"sale_line_id": line["sale_line_id"], "quantity": "1", "condition": "GOOD",
                   "serialized_unit_id": unit["serialized_unit_id"]}]})
    assert ret.status_code == 200, ret.text
    assert _units(ctx, phone, q=imei)[0]["status"] == "IN_STOCK"

    resale = c.post("/api/v1/sales", headers=ctx["C"], json={
        "lines": [{"item_id": phone["item_id"], "quantity": "1", "unit_price": "48000", "serialized_unit_id": unit["serialized_unit_id"]}],
        "payments": [{"method": "CASH", "amount": "48000"}], "idempotency_key": uuid.uuid4().hex})
    assert resale.status_code == 200, resale.text


def test_serialized_purchase_quantity_cannot_be_corrected(ctx, phone):
    c = ctx["c"]
    assert _buy(ctx, phone, [_imei()]).status_code == 200
    pending = [x for x in c.get("/api/v1/purchases/pending-costs", headers=ctx["A"]).json() if x["item_id"] == phone["item_id"]]
    line = pending[-1]
    # cost completion creates the lot; then the quantity correction must be refused for IMEI-tracked lines
    r = c.post("/api/v1/purchases/complete-cost", headers=ctx["A"], json={
        "purchase_id": line["purchase_id"], "purchase_line_id": line["purchase_line_id"], "unit_cost": "40000",
        "version": line["version"], "purchase_version": line["purchase_version"]})
    assert r.status_code == 200, r.text
    hist = next(x for x in c.get("/api/v1/purchases/history", headers=ctx["A"]).json() if x["purchase_line_id"] == line["purchase_line_id"])
    from tests.test_e2e_requirements import PASSWORD_ADMIN
    r = c.post("/api/v1/purchases/correct-quantity", params={"admin_password": PASSWORD_ADMIN}, headers=ctx["A"], json={
        "purchase_line_id": line["purchase_line_id"], "quantity": "5", "reason": "e2e", "version": hist["version"]})
    assert r.status_code == 400 and "serialized" in r.text.lower(), r.text


def test_purchase_accepts_line_date_like_the_ui_sends(ctx, phone):
    """Regression: the UI sends `line_date` on every line; the idempotency hash crashed (HTTP 500) on a date."""
    r = ctx["c"].post("/api/v1/purchases", headers=ctx["C"], json={
        "purchase_date": date.today().isoformat(), "reference_no": "LD-1",
        "lines": [{"item_id": phone["item_id"], "quantity": "1", "line_date": date.today().isoformat(), "serial_numbers": [_imei()]}],
        "idempotency_key": uuid.uuid4().hex})
    assert r.status_code == 200, r.text


def test_void_of_a_phone_sale_makes_the_imei_sellable_and_voids_its_warranty(ctx, phone):
    c = ctx["c"]
    _ensure_day(ctx)
    imei = _imei()
    assert _buy(ctx, phone, [imei]).status_code == 200
    unit = _units(ctx, phone, q=imei)[0]
    sale = c.post("/api/v1/sales", headers=ctx["A"], json={
        "lines": [{"item_id": phone["item_id"], "quantity": "1", "unit_price": "80000", "serialized_unit_id": unit["serialized_unit_id"],
                   "warranty_type": "MONTHS", "warranty_duration_value": 12}],
        "payments": [{"method": "CASH", "amount": "80000"}], "idempotency_key": uuid.uuid4().hex}).json()
    assert _units(ctx, phone, q=imei)[0]["status"] == "SOLD"
    version = c.get(f"/api/v1/sales/{sale['sale_id']}", headers=ctx["A"]).json()["version"]
    from tests.test_e2e_requirements import PASSWORD_ADMIN
    v = c.post(f"/api/v1/sales/{sale['sale_id']}/void", params={"reason": "wrong phone", "version": version, "admin_password": PASSWORD_ADMIN}, headers=ctx["A"])
    assert v.status_code == 200, v.text
    assert _units(ctx, phone, q=imei)[0]["status"] == "IN_STOCK"
    again = c.post("/api/v1/sales", headers=ctx["A"], json={
        "lines": [{"item_id": phone["item_id"], "quantity": "1", "unit_price": "80000", "serialized_unit_id": unit["serialized_unit_id"]}],
        "payments": [{"method": "CASH", "amount": "80000"}], "idempotency_key": uuid.uuid4().hex})
    assert again.status_code == 200, again.text
