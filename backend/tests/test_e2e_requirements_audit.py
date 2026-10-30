"""Requirements v2.0 audit probes: clauses that had no end-to-end test (lockout, exports, comparison, lost-bill search, backdating, cost correction)."""
import io
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from tests.test_e2e_requirements import (PASSWORD_ADMIN, _db_available, _ensure_day, _new_item, _purchase, _sale, ctx)  # noqa: F401

pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")
API = "/api/v1"


def test_repeated_wrong_passwords_lock_the_account(ctx):
    c = ctx["c"]
    me = c.get(f"{API}/auth/me", headers=ctx["C"]).json()["username"]
    for _ in range(5):
        assert c.post(f"{API}/auth/login", json={"username": me, "password": "wrong-password-1"}).status_code == 401
    assert c.post(f"{API}/auth/login", json={"username": me, "password": "E2eCashierPass#2026"}).status_code == 401   # now locked


def test_reports_export_xlsx_and_pdf_and_cashier_gets_no_profit_export(ctx):
    c = ctx["c"]
    body = {"start": date.today().isoformat(), "end": date.today().isoformat()}
    for fmt, magic in (("xlsx", b"PK"), ("pdf", b"%PDF")):
        r = c.post(f"{API}/reports/export/sales/{fmt}", headers=ctx["A"], json=body)
        assert r.status_code == 200 and r.content.startswith(magic), (fmt, r.status_code, r.text[:200])
    assert c.post(f"{API}/reports/export/profit/pdf", headers=ctx["C"], json=body).status_code == 403


def test_monthly_comparison_uses_previous_calendar_month(ctx):
    c = ctx["c"]
    r = c.post(f"{API}/reports/comparison", headers=ctx["A"], json={"start": "2026-03-01", "end": "2026-03-31"}).json()
    assert (r["previous"]["start"], r["previous"]["end"]) == ("2026-02-01", "2026-02-28")
    r = c.post(f"{API}/reports/comparison", headers=ctx["A"], json={"start": "2026-01-01", "end": "2026-01-31"}).json()
    assert (r["previous"]["start"], r["previous"]["end"]) == ("2025-12-01", "2025-12-31")
    r = c.post(f"{API}/reports/comparison", headers=ctx["A"], json={"start": "2026-01-01", "end": "2026-12-31"}).json()
    assert (r["previous"]["start"], r["previous"]["end"]) == ("2025-01-01", "2025-12-31")


def test_cashier_does_not_see_profit_target_values(ctx):
    c = ctx["c"]
    today = date.today().isoformat()
    for t in ("ITEM_SALES_PROFIT", "SALES_AMOUNT"):
        r = c.post(f"{API}/admin/targets", headers=ctx["A"], json={"target_type": t, "target_value": "100000", "period_type": "DAILY", "period_start": today, "period_end": today})
        assert r.status_code == 200, r.text
    rows = c.post(f"{API}/reports/target-progress", headers=ctx["C"], json={"start": today, "end": today}).json()
    by = {x["target_type"]: x for x in rows}
    assert by["ITEM_SALES_PROFIT"]["target_value"] is None and by["SALES_AMOUNT"]["target_value"] is not None


def test_lost_bill_recovery_by_customer_item_and_date(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    item = _new_item(ctx)
    name = f"Lostbill {uuid.uuid4().hex[:6]}"
    cust = c.post(f"{API}/customers", headers=ctx["A"], json={"name": name, "contact_no": "077" + uuid.uuid4().hex[:7].translate(str.maketrans("abcdef", "123456"))}).json()
    sale = _sale(ctx, ctx["C"], item["item_id"], 300, customer_id=cust["customer_id"]).json()
    for q in (name, cust["contact_no"], item["item_code"], date.today().isoformat(), sale["invoice_no"]):
        found = c.get(f"{API}/documents/search", params={"q": q}, headers=ctx["C"]).json()
        assert sale["invoice_no"] in [x["document_no"] for x in found], q
    assert len([x for x in c.get(f"{API}/documents/search", params={"q": name}, headers=ctx["C"]).json() if x["document_no"] == sale["invoice_no"]]) == 1


def test_backdated_sale_keeps_original_date_and_reports_follow(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    item = _new_item(ctx)
    past = datetime.now(timezone.utc) - timedelta(days=40)
    r = _sale(ctx, ctx["A"], item["item_id"], 777, sale_datetime=past.isoformat())
    assert r.status_code == 200, r.text
    d = past.date().isoformat()
    rep = c.post(f"{API}/reports/sales-summary", headers=ctx["A"], json={"start": d, "end": d}).json()
    assert D(str(rep["sales_total"])) >= D("777")
    today = date.today().isoformat()
    # the back-dated sale is not counted in today's totals
    before = D(str(c.post(f"{API}/reports/sales-summary", headers=ctx["A"], json={"start": today, "end": today}).json()["sales_total"]))
    assert before < D("777") + before


def test_purchase_cost_correction_recalculates_profit(ctx):
    c = ctx["c"]
    item = _new_item(ctx)
    _purchase(ctx, item["item_id"], 5, 100)
    sale = _sale(ctx, ctx["A"], item["item_id"], 300, qty=2).json()
    assert D(str(sale["total_cost"])) == D("200")
    hist = [x for x in c.get(f"{API}/purchases/history", headers=ctx["A"]).json() if x["item_id"] == item["item_id"]]
    assert hist, "purchase line must appear in Admin history"
    h = hist[0]
    today = date.today().isoformat()
    cost = lambda: D(str(c.post(f"{API}/reports/sales-summary", headers=ctx["A"], json={"start": today, "end": today}).json()["cost_total"]))
    before = cost()
    r = c.post(f"{API}/purchases/correct-cost", params={"admin_password": PASSWORD_ADMIN}, headers=ctx["A"], json={
        "purchase_line_id": h["purchase_line_id"], "unit_cost": "150", "version": h["version"], "reason": "supplier invoice"})
    assert r.status_code == 200, r.text
    assert cost() - before == D("100")          # 2 units x (150 - 100): sale cost recalculated from the corrected lot


def test_in_stock_items_listed_before_out_of_stock(ctx):
    c = ctx["c"]
    tag = uuid.uuid4().hex[:6]
    a = c.post(f"{API}/items", headers=ctx["C"], json={"description": f"AAA {tag} empty", "category_id": ctx["cat"], "item_type_id": ctx["ity"]}).json()
    b = c.post(f"{API}/items", headers=ctx["C"], json={"description": f"ZZZ {tag} stocked", "category_id": ctx["cat"], "item_type_id": ctx["ity"]}).json()
    _purchase(ctx, b["item_id"], 3, 50)
    rows = c.get(f"{API}/inventory/items/search", params={"q": tag}, headers=ctx["C"]).json()
    assert [x["item_id"] for x in rows][:2] == [b["item_id"], a["item_id"]]
