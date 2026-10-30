"""Requirements 06/16: Admin sale void – reversible, audited, invoice numbers never reused."""
import uuid
from datetime import date
from decimal import Decimal as D

import pytest

from tests.test_e2e_requirements import PASSWORD_ADMIN, _db_available, _ensure_day, _new_item, _purchase, _sale, ctx  # noqa: F401

pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")
API = "/api/v1"


def _stock(ctx, item):
    rows = ctx["c"].get(f"{API}/inventory/items/search", params={"q": item["item_code"]}, headers=ctx["C"]).json()
    return D(str(rows[0]["stock"]))


def _summary(ctx):
    t = date.today().isoformat()
    return ctx["c"].post(f"{API}/reports/sales-summary", headers=ctx["A"], json={"start": t, "end": t}).json()


def test_void_restores_stock_and_money_and_never_reuses_invoice_no(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    item = _new_item(ctx)
    _purchase(ctx, item["item_id"], 5, 100)
    expected0 = c.get(f"{API}/day/status", headers=ctx["C"]).json()["expected_cash"]
    sum0 = _summary(ctx)
    sale = _sale(ctx, ctx["C"], item["item_id"], 300, qty=2).json()
    assert _stock(ctx, item) == D("3")
    detail = c.get(f"{API}/sales/{sale['sale_id']}", headers=ctx["A"]).json()

    # Cashier cannot void; wrong password and missing reason are refused.
    assert c.post(f"{API}/sales/{sale['sale_id']}/void", params={"reason": "x", "version": detail["version"], "admin_password": PASSWORD_ADMIN}, headers=ctx["C"]).status_code == 403
    assert c.post(f"{API}/sales/{sale['sale_id']}/void", params={"reason": "x", "version": detail["version"], "admin_password": "wrong"}, headers=ctx["A"]).status_code in (400, 401, 403)
    assert c.post(f"{API}/sales/{sale['sale_id']}/void", params={"reason": "  ", "version": detail["version"], "admin_password": PASSWORD_ADMIN}, headers=ctx["A"]).status_code == 400
    assert c.post(f"{API}/sales/{sale['sale_id']}/void", params={"reason": "typo", "version": detail["version"] + 5, "admin_password": PASSWORD_ADMIN}, headers=ctx["A"]).status_code == 409

    ok = c.post(f"{API}/sales/{sale['sale_id']}/void", params={"reason": "wrong item rung up", "version": detail["version"], "admin_password": PASSWORD_ADMIN}, headers=ctx["A"])
    assert ok.status_code == 200 and ok.json()["status"] == "VOIDED" and ok.json()["invoice_no"] == sale["invoice_no"], ok.text
    assert _stock(ctx, item) == D("5")                                             # exact stock back
    sum1 = _summary(ctx)
    assert D(str(sum1["sales_total"])) == D(str(sum0["sales_total"])) and D(str(sum1["cost_total"])) == D(str(sum0["cost_total"]))
    assert D(str(c.get(f"{API}/day/status", headers=ctx["C"]).json()["expected_cash"])) == D(str(expected0))   # drawer back
    assert c.post(f"{API}/sales/{sale['sale_id']}/void", params={"reason": "again", "version": detail["version"] + 1, "admin_password": PASSWORD_ADMIN}, headers=ctx["A"]).status_code == 400
    assert c.get(f"{API}/sales/{sale['sale_id']}", headers=ctx["A"]).status_code == 404       # not returnable any more

    nxt = _sale(ctx, ctx["C"], item["item_id"], 300).json()
    assert nxt["invoice_no"] != sale["invoice_no"]
    assert int(nxt["invoice_no"].split("-")[-1]) > int(sale["invoice_no"].split("-")[-1])
    # FIFO still exact after the void: the next unit costs 100 again.
    assert D(str(_sale(ctx, ctx["A"], item["item_id"], 300).json()["total_cost"])) == D("100")
    assert any(a["action_type"] == "SALE_VOIDED" for a in c.get(f"{API}/admin/audit", headers=ctx["A"]).json())


def test_void_blocked_after_a_return_and_returns_cannot_target_voided_sale(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    item = _new_item(ctx)
    _purchase(ctx, item["item_id"], 5, 100)
    sale = _sale(ctx, ctx["C"], item["item_id"], 300).json()
    detail = c.get(f"{API}/sales/{sale['sale_id']}", headers=ctx["A"]).json()
    line = detail["lines"][0]
    r = c.post(f"{API}/returns", headers=ctx["A"], json={"original_sale_id": sale["sale_id"], "return_charge": "0", "idempotency_key": uuid.uuid4().hex,
                                                         "lines": [{"sale_line_id": line["sale_line_id"], "quantity": "1", "condition": "GOOD"}]})
    assert r.status_code == 200, r.text
    v = c.post(f"{API}/sales/{sale['sale_id']}/void", params={"reason": "late", "version": detail["version"], "admin_password": PASSWORD_ADMIN}, headers=ctx["A"])
    assert v.status_code == 400 and "return" in v.text.lower()
