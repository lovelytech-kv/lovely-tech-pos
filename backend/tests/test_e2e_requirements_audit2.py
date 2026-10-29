"""Requirements v2.0 audit, batch 2: credit/settlement, barcodes, item codes, warranty, negative-stock reconcile, audit log, return window, Day End."""
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D

import pytest
from sqlalchemy import create_engine, text

from app.core.config import settings
from tests.test_e2e_requirements import PASSWORD_ADMIN, _db_available, _ensure_day, _new_item, _purchase, _sale, ctx  # noqa: F401

pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")
API = "/api/v1"


def _summary(ctx):
    t = date.today().isoformat()
    return ctx["c"].post(f"{API}/reports/sales-summary", headers=ctx["A"], json={"start": t, "end": t}).json()


def test_credit_sale_revenue_now_settlement_is_not_new_revenue(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    item = _new_item(ctx)
    _purchase(ctx, item["item_id"], 3, 100)
    cust = c.post(f"{API}/customers", headers=ctx["A"], json={"name": "Credit " + uuid.uuid4().hex[:5], "contact_no": "071" + str(uuid.uuid4().int)[:7]}).json()
    before = _summary(ctx)
    r = c.post(f"{API}/sales", headers=ctx["A"], json={"lines": [{"item_id": item["item_id"], "quantity": "1", "unit_price": "1000"}], "payments": [],
                                                      "credit_sale": True, "customer_id": cust["customer_id"], "idempotency_key": uuid.uuid4().hex})
    assert r.status_code == 200, r.text
    mid = _summary(ctx)
    assert D(str(mid["sales_total"])) - D(str(before["sales_total"])) == D("1000")
    assert D(str(mid["gross_profit"])) - D(str(before["gross_profit"])) == D("900")
    s = c.post(f"{API}/settlements", headers=ctx["A"], json={"customer_id": cust["customer_id"], "amount": "400", "payment_method": "CASH", "idempotency_key": uuid.uuid4().hex})
    assert s.status_code == 200, s.text
    after = _summary(ctx)
    assert D(str(after["sales_total"])) == D(str(mid["sales_total"])) and D(str(after["gross_profit"])) == D(str(mid["gross_profit"]))
    hist = c.get(f"{API}/customers/{cust['customer_id']}/history", headers=ctx["A"]).json()
    st = hist["settlements"][0]
    assert D(str(st["remaining"])) == D("600") and D(str(st["amount"])) == D("400")


def test_multiple_barcodes_find_the_item_and_duplicates_are_refused(ctx):
    c = ctx["c"]
    item = _new_item(ctx)
    b1, b2 = "BC" + uuid.uuid4().hex[:10], "BC" + uuid.uuid4().hex[:10]
    assert c.post(f"{API}/items/{item['item_id']}/barcodes", headers=ctx["C"], json={"barcode": b1, "is_primary": True}).status_code == 200
    assert c.post(f"{API}/items/{item['item_id']}/barcodes", headers=ctx["C"], json={"barcode": b2, "is_primary": False}).status_code == 200
    for b in (b1, b2):
        rows = c.get(f"{API}/inventory/items/search", params={"q": b}, headers=ctx["C"]).json()
        assert [x["item_id"] for x in rows] == [item["item_id"]]
    other = _new_item(ctx)
    assert c.post(f"{API}/items/{other['item_id']}/barcodes", headers=ctx["C"], json={"barcode": b1, "is_primary": True}).status_code == 409


def test_item_codes_are_sequential(ctx):
    a, b = _new_item(ctx), _new_item(ctx)
    assert int(b["item_code"][3:]) == int(a["item_code"][3:]) + 1


def test_warranty_copied_at_sale_time_and_later_master_change_does_not_rewrite_it(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    item = _new_item(ctx)
    _purchase(ctx, item["item_id"], 3, 100)
    c.put(f"{API}/items/{item['item_id']}/warranty-default", headers=ctx["A"], json={"warranty_type": "MONTHS", "duration_value": 6})
    sale = _sale(ctx, ctx["C"], item["item_id"], 500).json()
    wid = sale["warranty_ids"]
    assert len(wid) == 1
    row = c.get(f"{API}/warranty/lookup", params={"warranty_no": c.get(f"{API}/warranty/claims", headers=ctx["A"]).json() and ""}, headers=ctx["C"])  # lookup needs a number; exercise below via DB
    eng = create_engine(settings.database_url)
    with eng.connect() as cn:
        w = cn.execute(text("select warranty_type, duration_value, start_date, expiry_date, status from product_warranties where id=:i"), {"i": wid[0]}).one()
    assert w.warranty_type == "MONTHS" and w.duration_value == 6 and w.status == "ACTIVE"
    assert (w.expiry_date - w.start_date).days in range(180, 186)
    c.put(f"{API}/items/{item['item_id']}/warranty-default", headers=ctx["A"], json={"warranty_type": "DAYS", "duration_value": 1})
    with eng.connect() as cn:
        w2 = cn.execute(text("select warranty_type, duration_value, expiry_date from product_warranties where id=:i"), {"i": wid[0]}).one()
    assert (w2.warranty_type, w2.duration_value, w2.expiry_date) == ("MONTHS", 6, w.expiry_date)
    # sale-time override
    s2 = _sale(ctx, ctx["C"], item["item_id"], 500)
    body = {"lines": [{"item_id": item["item_id"], "quantity": "1", "unit_price": "500", "warranty_type": "DAYS", "warranty_duration_value": 10}],
            "payments": [{"method": "CASH", "amount": "500"}], "idempotency_key": uuid.uuid4().hex}
    s3 = c.post(f"{API}/sales", headers=ctx["C"], json=body).json()
    with eng.connect() as cn:
        w3 = cn.execute(text("select warranty_type, duration_value from product_warranties where id=:i"), {"i": s3["warranty_ids"][0]}).one()
    assert (w3.warranty_type, w3.duration_value) == ("DAYS", 10)


def test_manual_invoice_requires_and_stores_the_handwritten_reference(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    item = _new_item(ctx)
    base = {"lines": [{"item_id": item["item_id"], "quantity": "1", "unit_price": "100"}], "payments": [{"method": "CASH", "amount": "100"}], "document_type": "MANUAL"}
    assert c.post(f"{API}/sales", headers=ctx["C"], json={**base, "idempotency_key": uuid.uuid4().hex}).status_code == 400
    ref = "HW-" + uuid.uuid4().hex[:6]
    ok = c.post(f"{API}/sales", headers=ctx["C"], json={**base, "manual_invoice_ref": ref, "idempotency_key": uuid.uuid4().hex})
    assert ok.status_code == 200, ok.text
    found = c.get(f"{API}/documents/search", params={"q": ref}, headers=ctx["C"]).json()
    assert ok.json()["invoice_no"] in [x["document_no"] for x in found]


def test_later_purchase_reconciles_earlier_negative_sale_cost(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    item = _new_item(ctx)
    sale = _sale(ctx, ctx["A"], item["item_id"], 500, qty=2).json()
    assert sale["negative_stock"] is True
    before = D(str(_summary(ctx)["cost_total"]))
    _purchase(ctx, item["item_id"], 5, 120)
    assert D(str(_summary(ctx)["cost_total"])) - before == D("240")      # 2 x 120 attached to the earlier sale
    rows = c.get(f"{API}/inventory/items/search", params={"q": item["item_code"]}, headers=ctx["C"]).json()
    assert D(str(rows[0]["stock"])) == D("3")


def test_audit_log_cannot_be_updated_or_deleted(ctx):
    eng = create_engine(settings.database_url)
    ctx["c"].get(f"{API}/admin/audit", headers=ctx["A"])
    with eng.begin() as cn:
        n = cn.execute(text("select count(*) from audit_log")).scalar()
    assert n > 0
    for stmt in ("update audit_log set reason='tamper'", "delete from audit_log"):
        with pytest.raises(Exception):
            with eng.begin() as cn:
                cn.execute(text(stmt))
    assert ctx["c"].get(f"{API}/admin/audit", headers=ctx["C"]).status_code == 403


def test_return_beyond_seven_days_is_admin_only(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    item = _new_item(ctx)
    _purchase(ctx, item["item_id"], 3, 100)
    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    sale = _sale(ctx, ctx["A"], item["item_id"], 400, sale_datetime=past).json()
    line = c.get(f"{API}/sales/{sale['sale_id']}", headers=ctx["A"]).json()["lines"][0]
    body = {"original_sale_id": sale["sale_id"], "lines": [{"sale_line_id": line["sale_line_id"], "quantity": "1", "condition": "GOOD"}], "idempotency_key": uuid.uuid4().hex}
    assert c.post(f"{API}/returns", headers=ctx["C"], json=body).status_code in (400, 403)
    body["idempotency_key"] = uuid.uuid4().hex
    assert c.post(f"{API}/returns", headers=ctx["A"], json={**body, "admin_override": True, "reason": "goodwill"}).status_code == 200


def test_day_end_needs_reason_and_reopen_is_admin_reauth_only(ctx):
    c = ctx["c"]
    st = _ensure_day(ctx)
    sid, ver = st["day_session_id"], st["version"]
    bad = c.post(f"{API}/day/{sid}/end", headers=ctx["C"], json={"version": ver, "actual_cash": "0", "denominations": {}, "reason": ""})
    assert bad.status_code in (400, 422)
    assert c.post(f"{API}/day/reopen", headers=ctx["C"], json={"start": date.today().isoformat(), "end": date.today().isoformat()}).status_code in (400, 401, 403)


def test_repair_part_compatible_models_are_searchable(ctx):
    c = ctx["c"]
    tag = uuid.uuid4().hex[:6].upper()
    r = c.post(f"{API}/items", headers=ctx["C"], json={"description": f"Display {tag}", "category_id": ctx["cat"], "item_type_id": ctx["ity"],
                                                       "model": f"A15-{tag}", "compatible_models": f"A16-{tag}, M14-{tag}"})
    assert r.status_code == 200 and r.json()["compatible_models"] == f"A16-{tag}, M14-{tag}", r.text
    for q in (f"A15-{tag}", f"M14-{tag}"):
        assert [x["item_id"] for x in c.get(f"{API}/inventory/items/search", params={"q": q}, headers=ctx["C"]).json()] == [r.json()["item_id"]], q
    assert c.get(f"{API}/items/admin-list", params={"q": f"A16-{tag}"}, headers=ctx["A"]).json()[0]["item_id"] == r.json()["item_id"]
