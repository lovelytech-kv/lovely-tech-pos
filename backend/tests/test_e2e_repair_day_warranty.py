"""End-to-end (HTTP -> services -> PostgreSQL) checks for Requirements v2.0 sections 09-12:
repairs, warranty, expenses/other income, and the Day/Shift lifecycle."""
import uuid
from datetime import date
from decimal import Decimal as D

import pytest

from tests.test_e2e_requirements import (  # noqa: F401  (ctx fixture + helpers are shared)
    _db_available, _ensure_day, _new_item, _purchase, _sale, ctx,
)

pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")


def _stock(ctx, item):
    r = ctx["c"].get(f"/api/v1/inventory/items/search?q={item['item_code']}", headers=ctx["C"])
    assert r.status_code == 200, r.text
    rows = [x for x in r.json() if str(x.get("item_id")) == str(item["item_id"])]
    assert rows, r.text
    return D(str(rows[0].get("stock_quantity", rows[0].get("quantity_on_hand", rows[0].get("stock")))))


def _repair(ctx, **extra):
    body = {"device_brand": "Samsung", "model": "A15", "customer_name": "E2E Customer", "contact_no": "0771234567",
            "reported_fault": "Display broken", "estimated_amount": "5000"}
    body.update(extra)
    r = ctx["c"].post("/api/v1/repairs", headers=ctx["C"], json=body)
    assert r.status_code == 200, r.text
    assert r.json()["repair_no"].startswith("REP-") and r.json()["status"] == "RECEIVED"
    return r.json()


def _detail(ctx, repair_id):
    r = ctx["c"].get(f"/api/v1/repairs/{repair_id}", headers=ctx["C"])
    assert r.status_code == 200, r.text
    return r.json()


def test_repair_lifecycle_parts_payments_and_delivery_with_outstanding(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    part = _new_item(ctx)
    _purchase(ctx, part["item_id"], 5, 1500)
    rep = _repair(ctx)
    rid = rep["repair_id"]

    r = c.post(f"/api/v1/repairs/{rid}/status", headers=ctx["C"], json={"status": "CHECKING", "version": _detail(ctx, rid)["version"]})
    assert r.status_code == 200, r.text

    before = _stock(ctx, part)
    r = c.post(f"/api/v1/repairs/{rid}/part", headers=ctx["C"], json={"item_id": part["item_id"], "quantity": "1", "charge_amount": "4000"})
    assert r.status_code == 200, r.text
    assert before - _stock(ctx, part) == D("1")  # parts deduct stock immediately

    d = _detail(ctx, rid)
    r = c.post(f"/api/v1/repairs/{rid}/finalize", headers=ctx["C"], json={
        "version": d["version"], "final_amount": "5000", "labour_amount": "1000"})
    assert r.status_code == 200, r.text

    # Advance + partial final payment, split across methods; outstanding stays.
    for method, amount in (("CASH", "2000"), ("CARD", "1000")):
        r = c.post(f"/api/v1/repairs/{rid}/payment", headers=ctx["C"], json={
            "method": method, "amount": amount, "idempotency_key": uuid.uuid4().hex})
        assert r.status_code == 200, r.text

    # Cashier cannot deliver with outstanding balance (needs Admin approval).
    d = _detail(ctx, rid)
    for status in ("REPAIRING", "READY"):
        r = c.post(f"/api/v1/repairs/{rid}/status", headers=ctx["C"], json={"status": status, "version": _detail(ctx, rid)["version"]})
        assert r.status_code == 200, r.text
    d = _detail(ctx, rid)
    r = c.post(f"/api/v1/repairs/{rid}/deliver?version={d['version']}", headers=ctx["C"])
    assert r.status_code == 400, r.text
    r = c.post(f"/api/v1/repairs/{rid}/deliver?version={d['version']}", headers=ctx["A"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "DELIVERED"


def test_repair_part_removal_good_restores_stock_damaged_goes_to_review(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    part = _new_item(ctx)
    _purchase(ctx, part["item_id"], 5, 800)
    rid = _repair(ctx)["repair_id"]
    for _ in range(2):
        r = c.post(f"/api/v1/repairs/{rid}/part", headers=ctx["C"], json={"item_id": part["item_id"], "quantity": "1", "charge_amount": "1500"})
        assert r.status_code == 200, r.text
    assert _stock(ctx, part) == D("3")
    parts = _detail(ctx, rid)["parts"]
    assert len(parts) == 2
    good, bad = parts[0], parts[1]
    gid = good.get("repair_part_id") or good.get("part_id") or good.get("id")
    bid = bad.get("repair_part_id") or bad.get("part_id") or bad.get("id")

    r = c.post(f"/api/v1/repairs/{rid}/part/{gid}/remove", headers=ctx["C"], json={"condition": "GOOD", "reason": "wrong part"})
    assert r.status_code == 200, r.text
    assert _stock(ctx, part) == D("4")  # good part restores its FIFO lot

    r = c.post(f"/api/v1/repairs/{rid}/part/{bid}/remove", headers=ctx["C"], json={"condition": "DAMAGED", "reason": "burnt"})
    assert r.status_code == 200, r.text
    assert _stock(ctx, part) == D("4")  # damaged part never returns to stock


def test_repair_cancel_returns_unused_parts(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    part = _new_item(ctx)
    _purchase(ctx, part["item_id"], 3, 500)
    rid = _repair(ctx)["repair_id"]
    assert c.post(f"/api/v1/repairs/{rid}/part", headers=ctx["C"], json={"item_id": part["item_id"], "quantity": "1", "charge_amount": "900"}).status_code == 200
    assert _stock(ctx, part) == D("2")
    r = c.post(f"/api/v1/repairs/{rid}/cancel", headers=ctx["C"], json={"version": _detail(ctx, rid)["version"], "reason": "customer left"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "CANCELLED"
    assert _stock(ctx, part) == D("3")


def test_cashier_expense_is_pending_and_excluded_until_admin_approves(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    cats = c.get("/api/v1/admin/expense-categories", headers=ctx["A"]).json()
    cat_id = next(x["id"] if "id" in x else x["category_id"] for x in cats)

    def cash_in_hands():
        r = c.post("/api/v1/reports/cash-in-hands", headers=ctx["A"],
                   json={"start": date.today().isoformat(), "end": date.today().isoformat()})
        assert r.status_code == 200, r.text
        return r.json()

    before = cash_in_hands()
    r = c.post("/api/v1/admin/expenses", headers=ctx["C"], json={
        "category_id": cat_id, "expense_date": date.today().isoformat(), "amount": "777", "payment_method": "CASH",
        "description": "e2e tea", "idempotency_key": uuid.uuid4().hex})
    assert r.status_code == 200, r.text
    expense_id = r.json().get("expense_id") or r.json().get("id")
    assert str(r.json().get("status", "PENDING")).upper().startswith("PENDING")
    assert cash_in_hands() == before  # pending entries are excluded from Cash In Hands

    pending = c.get("/api/v1/admin/pending-expenses", headers=ctx["A"]).json()
    assert any(str(p.get("expense_id") or p.get("id")) == str(expense_id) for p in pending)
    assert c.get("/api/v1/admin/pending-expenses", headers=ctx["C"]).status_code == 403
    row = next(p for p in pending if str(p.get("expense_id") or p.get("id")) == str(expense_id))
    r = c.post(f"/api/v1/admin/expenses/{expense_id}/decision?approve=true&version={row.get('version')}", headers=ctx["A"])
    assert r.status_code == 200, r.text
    assert cash_in_hands() != before  # approved -> now counted


def test_reload_is_entered_once_per_business_day(ctx):
    c = ctx["c"]
    day = _ensure_day(ctx)
    day_id = day["day_session_id"]
    body = {"day_session_id": day_id, "provider": "Dialog", "amount": "5000", "version": day.get("version")}
    first = c.post("/api/v1/day/reload", headers=ctx["C"], json=body)
    # The test day may already hold a reload from an earlier run: that itself must be a rejection.
    assert first.status_code == 200 or (first.status_code in (400, 409) and "reload" in first.text.lower()), first.text
    day = c.get("/api/v1/day/status", headers=ctx["C"]).json()
    second = c.post("/api/v1/day/reload", headers=ctx["C"], json={**body, "provider": "Airtel", "version": day.get("version")})
    assert second.status_code in (400, 409), second.text
    assert "reload" in second.text.lower()


def test_warranty_claim_requires_admin_decision_and_cashier_cannot_decide(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    item = _new_item(ctx)
    _purchase(ctx, item["item_id"], 2, 1000)
    assert _sale(ctx, ctx["C"], item["item_id"], 1800).status_code == 200
    claim = c.post("/api/v1/warranty/claims", headers=ctx["C"], json={"item_id": item["item_id"], "quantity": "1", "notes": "e2e dead on arrival"})
    assert claim.status_code == 200, claim.text
    claim_id = claim.json().get("claim_id") or claim.json().get("id")
    assert claim_id
    # Cashier creates the claim but cannot decide supplier-claim vs damage/loss.
    r = c.post(f"/api/v1/warranty/claims/{claim_id}/supplier", headers=ctx["C"], json={"supplier_process": "SUPPLIER_WARRANTY_CLAIM"})
    assert r.status_code == 403
    claims = c.get("/api/v1/warranty/claims", headers=ctx["A"]).json()
    mine = next(x for x in claims if str(x.get("claim_id") or x.get("id")) == str(claim_id))
    r = c.post(f"/api/v1/warranty/claims/{claim_id}/supplier", headers=ctx["A"], json={
        "supplier_process": "SUPPLIER_WARRANTY_CLAIM", "version": mine.get("version")})
    assert r.status_code == 200, r.text


def test_shift_end_requires_verified_backup_then_day_cannot_start_twice(ctx):
    c = ctx["c"]
    day = _ensure_day(ctx)
    # Requirements 15: Shift End / Day End require a verified backup.
    r = c.post("/api/v1/day/shift-end", headers=ctx["C"], json={"start": date.today().isoformat(), "end": date.today().isoformat()})
    assert r.status_code == 409 and "backup" in r.text.lower(), r.text
    dup = c.post("/api/v1/day/start", headers=ctx["C"], json={
        "business_date": date.today().isoformat(), "opening_cash": "1000", "denominations": {"1000": 1}})
    assert dup.status_code in (400, 409), dup.text
    assert day["status"] == "OPEN"
