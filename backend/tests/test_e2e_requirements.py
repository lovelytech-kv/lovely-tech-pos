"""Real end-to-end checks (HTTP -> services -> PostgreSQL) of key Requirements v2.0 rules.

Unlike the source-text contract tests, these exercise the running application, so they catch
crashes such as POST /returns raising TypeError or POST /returns/exchange hitting a NOT NULL
violation. Every run uses a unique item, so it can share a database with other tests.
"""
import os
import subprocess
import sys
import uuid
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.main import app

ROOT = Path(__file__).resolve().parents[2]
PASSWORD_ADMIN = "E2eAdminPass#2026"
PASSWORD_CASHIER = "E2eCashierPass#2026"


def _db_available() -> bool:
    try:
        with create_engine(settings.database_url).connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")


@pytest.fixture(scope="module")
def ctx():
    """Provision users with the real bootstrap script, then log in through the API."""
    suffix = uuid.uuid4().hex[:8]
    env = dict(os.environ, ADMIN_USERNAME=f"e2e_admin_{suffix}", ADMIN_PASSWORD=PASSWORD_ADMIN,
               CASHIER_USERNAME=f"e2e_cashier_{suffix}", CASHIER_PASSWORD=PASSWORD_CASHIER)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "bootstrap_security.py")], cwd=ROOT / "backend",
                   env=env, check=True, capture_output=True)
    client = TestClient(app)

    def login(user, password):
        r = client.post("/api/v1/auth/login", json={"username": user, "password": password})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    admin = login(env["ADMIN_USERNAME"], PASSWORD_ADMIN)
    cashier = login(env["CASHIER_USERNAME"], PASSWORD_CASHIER)
    cat = client.post("/api/v1/items/categories", headers=admin, json={"name": f"E2E-{suffix}"}).json()
    ity = client.post("/api/v1/items/item-types", headers=admin,
                      json={"code": f"E2E{suffix}", "name": f"E2E-{suffix}", "is_serialized": False}).json()
    return {"c": client, "A": admin, "C": cashier, "cat": cat["id"], "ity": ity["id"], "suffix": suffix}


def _new_item(ctx, headers=None):
    r = ctx["c"].post("/api/v1/items", headers=headers or ctx["C"], json={
        "description": f"E2E item {uuid.uuid4().hex[:6]}", "category_id": ctx["cat"], "item_type_id": ctx["ity"]})
    assert r.status_code == 200, r.text
    return r.json()


def _purchase(ctx, item_id, qty, unit_cost):
    c = ctx["c"]
    r = c.post("/api/v1/purchases", headers=ctx["C"], json={
        "purchase_date": date.today().isoformat(), "reference_no": f"E2E-{uuid.uuid4().hex[:6]}",
        "lines": [{"item_id": item_id, "quantity": str(qty)}], "idempotency_key": uuid.uuid4().hex})
    assert r.status_code == 200, r.text
    pid = r.json()["purchase_id"]
    pending = [x for x in c.get("/api/v1/purchases/pending-costs", headers=ctx["A"]).json() if x["purchase_id"] == pid]
    assert len(pending) == 1
    line = pending[0]
    r = c.post("/api/v1/purchases/complete-cost", headers=ctx["A"], json={
        "purchase_id": pid, "purchase_line_id": line["purchase_line_id"], "unit_cost": str(unit_cost),
        "version": line["version"], "purchase_version": line["purchase_version"]})
    assert r.status_code == 200, r.text


def _sale(ctx, headers, item_id, price, qty=1, **extra):
    body = {"lines": [{"item_id": item_id, "quantity": str(qty), "unit_price": str(price)}],
            "payments": [{"method": "CASH", "amount": str(D(str(price)) * D(str(qty)))}],
            "idempotency_key": uuid.uuid4().hex}
    body.update(extra)
    return ctx["c"].post("/api/v1/sales", headers=headers, json=body)


def _ensure_day(ctx):
    c = ctx["c"]
    r = c.get("/api/v1/day/status", headers=ctx["C"])
    if r.status_code == 200 and r.json().get("status") == "OPEN":
        return r.json()
    if r.status_code == 200 and r.json().get("status") == "SHIFT_ENDED":  # an earlier test ended the shift: reopen it
        cont = c.post("/api/v1/day/continue", headers=ctx["A"], json={"start": date.today().isoformat(), "end": date.today().isoformat()})
        assert cont.status_code == 200, cont.text
        return c.get("/api/v1/day/status", headers=ctx["C"]).json()
    r = c.post("/api/v1/day/start", headers=ctx["C"], json={
        "business_date": date.today().isoformat(), "opening_cash": "1000", "denominations": {"1000": 1}})
    assert r.status_code == 200, r.text
    return c.get("/api/v1/day/status", headers=ctx["C"]).json()


def test_cashier_can_create_item_with_lvt_code(ctx):
    item = _new_item(ctx)  # Requirements 02/04: cashier basic item entry, code such as LVT0001
    assert item["item_code"].startswith("LVT") and item["item_code"][3:].isdigit() and len(item["item_code"]) >= 7


def test_cashier_cannot_preserve_imported_item_code(ctx):
    r = ctx["c"].post("/api/v1/items", headers=ctx["C"], json={
        "description": "x", "item_code": "LVT9999", "category_id": ctx["cat"], "item_type_id": ctx["ity"]})
    assert r.status_code == 403


def test_fifo_cost_across_lots_and_cashier_never_sees_cost(ctx):
    item = _new_item(ctx)
    _purchase(ctx, item["item_id"], 10, 100)
    _purchase(ctx, item["item_id"], 10, 120)
    # 12 units consume 10 @100 and 2 @120 = 1240 exact FIFO cost (Requirements 05).
    r = _sale(ctx, ctx["A"], item["item_id"], 200, qty=12)
    assert r.status_code == 200, r.text
    assert D(str(r.json()["total_cost"])) == D("1240")
    # Cashier receives no cost anywhere in the sale response or the item search.
    r = _sale(ctx, ctx["C"], item["item_id"], 200)
    assert r.status_code == 200 and r.json()["total_cost"] is None
    search = ctx["c"].get(f"/api/v1/inventory/items/search?q={item['item_code']}", headers=ctx["C"]).text.lower()
    assert not any(word in search for word in ("cost", "supplier", "profit"))


def test_negative_stock_is_allowed_and_flagged(ctx):
    item = _new_item(ctx)
    r = _sale(ctx, ctx["C"], item["item_id"], 100, qty=3)
    assert r.status_code == 200 and r.json()["negative_stock"] is True


def test_sale_idempotency_replays_same_sale(ctx):
    item = _new_item(ctx)
    key = uuid.uuid4().hex
    first = _sale(ctx, ctx["C"], item["item_id"], 100, idempotency_key=key)
    second = _sale(ctx, ctx["C"], item["item_id"], 100, idempotency_key=key)
    assert first.status_code == second.status_code == 200
    assert first.json()["sale_id"] == second.json()["sale_id"]


def test_cashier_blocked_from_credit_sale_and_excess_discount(ctx):
    item = _new_item(ctx)
    r = _sale(ctx, ctx["C"], item["item_id"], 200, credit_sale=True, payments=[])
    assert r.status_code in (400, 403)
    r = ctx["c"].post("/api/v1/sales", headers=ctx["C"], json={
        "lines": [{"item_id": item["item_id"], "quantity": "1", "unit_price": "200", "discount": "50"}],
        "payments": [{"method": "CASH", "amount": "150"}], "idempotency_key": uuid.uuid4().hex})
    assert r.status_code in (400, 403, 409)


def test_return_with_charge_then_exchange_matches_requirements_example(ctx):
    """Requirements 07: old 1000, charge 200 -> refund 800; new item 1500; net drawer +700."""
    c = ctx["c"]
    item = _new_item(ctx)
    _ensure_day(ctx)
    old = _sale(ctx, ctx["C"], item["item_id"], 1000)
    assert old.status_code == 200, old.text
    sale = c.get(f"/api/v1/sales/{old.json()['sale_id']}", headers=ctx["C"]).json()
    line_id = sale["lines"][0]["sale_line_id"]

    ret = c.post("/api/v1/returns", headers=ctx["C"], json={
        "original_sale_id": sale["sale_id"], "lines": [{"sale_line_id": line_id, "quantity": "1", "condition": "GOOD"}],
        "return_charge": "200", "reason": "e2e", "idempotency_key": uuid.uuid4().hex})
    assert ret.status_code == 200, ret.text  # regression: used to crash with TypeError (HTTP 500)
    assert D(str(ret.json()["refund_total"])) == D("800")
    assert D(str(ret.json()["return_charge"])) == D("200")

    new_sale = _sale(ctx, ctx["C"], item["item_id"], 1500)
    assert new_sale.status_code == 200, new_sale.text
    ex = c.post("/api/v1/returns/exchange", headers=ctx["C"], json={
        "return_id": ret.json()["return_id"], "replacement_sale_id": new_sale.json()["sale_id"]})
    assert ex.status_code == 200, ex.text  # regression: used to violate document_events.document_id NOT NULL
    assert D(str(ex.json()["difference_amount"])) == D("700")
    # An exchange links a return to exactly one separate sale; it cannot be linked twice.
    again = c.post("/api/v1/returns/exchange", headers=ctx["C"], json={
        "return_id": ret.json()["return_id"], "replacement_sale_id": new_sale.json()["sale_id"]})
    assert again.status_code == 400


def test_cash_drawer_moves_with_cash_sales_and_refund_payments_only(ctx):
    c = ctx["c"]
    item = _new_item(ctx)
    _ensure_day(ctx)

    def expected():
        return D(str(c.get("/api/v1/day/status", headers=ctx["C"]).json()["expected_cash"]))

    before = expected()
    assert _sale(ctx, ctx["C"], item["item_id"], 500).status_code == 200
    assert expected() - before == D("500")
    card = c.post("/api/v1/sales", headers=ctx["C"], json={
        "lines": [{"item_id": item["item_id"], "quantity": "1", "unit_price": "300"}],
        "payments": [{"method": "CARD", "amount": "300"}], "idempotency_key": uuid.uuid4().hex})
    assert card.status_code == 200
    assert expected() - before == D("500")  # Card/Online never enter the physical drawer

    sale_id = _sale(ctx, ctx["C"], item["item_id"], 1000).json()["sale_id"]
    line_id = c.get(f"/api/v1/sales/{sale_id}", headers=ctx["C"]).json()["lines"][0]["sale_line_id"]
    ret = c.post("/api/v1/returns", headers=ctx["C"], json={
        "original_sale_id": sale_id, "lines": [{"sale_line_id": line_id, "quantity": "1", "condition": "GOOD"}],
        "return_charge": "200", "idempotency_key": uuid.uuid4().hex}).json()
    mid = expected()
    pay = c.post(f"/api/v1/returns/{ret['return_id']}/refund-payment", headers=ctx["C"], json={
        "payment_method": "CASH", "amount": "800", "idempotency_key": uuid.uuid4().hex})
    assert pay.status_code == 200, pay.text
    assert mid - expected() == D("800")


def test_cashier_cannot_reach_admin_only_data(ctx):
    c = ctx["c"]
    for path in ("/api/v1/purchases/history", "/api/v1/purchases/pending-costs", "/api/v1/backup/points",
                 "/api/v1/admin/audit"):
        assert c.get(path, headers=ctx["C"]).status_code == 403, path
        assert c.get(path, headers=ctx["A"]).status_code == 200, path
    report = c.post("/api/v1/reports/sales-summary", headers=ctx["C"], json={"start": "2026-01-01", "end": "2026-12-31"}).json()
    assert all(report.get(k) is None for k in ("gross_profit", "cost_total", "net_profit", "return_charge_total"))


def test_admin_report_includes_return_charge_income(ctx):
    start = date.today().replace(day=1).isoformat()
    report = ctx["c"].post("/api/v1/reports/sales-summary", headers=ctx["A"],
                           json={"start": start, "end": date.today().isoformat()}).json()
    assert D(str(report["return_charge_total"])) >= D("200")
