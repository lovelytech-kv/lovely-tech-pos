"""Requirements 07: a resellable damaged item is restocked by Admin through an audited reversal; profit gets the loss back."""
import uuid
from decimal import Decimal as D
from datetime import date

import pytest

from tests.test_e2e_requirements import PASSWORD_ADMIN, _db_available, _ensure_day, _new_item, _purchase, ctx  # noqa: F401

pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")
API = "/api/v1"




def test_admin_restock_reverses_damage_with_audit_and_profit(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    item = _new_item(ctx)
    _purchase(ctx, item["item_id"], 10, 100)
    today = date.today().isoformat()
    summary = lambda: c.post(f"{API}/reports/sales-summary", headers=ctx["A"], json={"start": today, "end": today}).json()
    loss0 = D(str(summary().get("damage_loss_total", 0)))
    dmg = c.post(f"{API}/stock-control/damage-loss", params={"admin_password": PASSWORD_ADMIN}, headers=ctx["A"],
                 json={"item_id": item["item_id"], "quantity": "2", "reason": "dropped"})
    assert dmg.status_code == 200, dmg.text
    did = dmg.json()["damage_loss_id"]
    assert D(str(summary()["damage_loss_total"])) - loss0 == D("200")

    url = f"{API}/stock-control/damage-loss/{did}/restock"
    assert c.post(url, params={"reason": "works fine", "admin_password": PASSWORD_ADMIN}, headers=ctx["C"]).status_code == 403
    assert c.post(url, params={"reason": "works fine", "admin_password": "wrong"}, headers=ctx["A"]).status_code in (400, 401, 403)
    assert c.post(url, params={"reason": " ", "admin_password": PASSWORD_ADMIN}, headers=ctx["A"]).status_code == 400
    ok = c.post(url, params={"reason": "works fine", "admin_password": PASSWORD_ADMIN}, headers=ctx["A"])
    assert ok.status_code == 200 and ok.json()["review_status"] == "RESTOCKED", ok.text
    assert D(str(summary()["damage_loss_total"])) == loss0                       # loss given back
    assert c.post(url, params={"reason": "again", "admin_password": PASSWORD_ADMIN}, headers=ctx["A"]).status_code == 400
    listed = c.get(f"{API}/stock-control/damage-loss", headers=ctx["A"]).json()
    assert [x["review_status"] for x in listed if x["damage_loss_id"] == did] == ["RESTOCKED"]
    assert any(a["action_type"] == "DAMAGE_RESTOCK" for a in c.get(f"{API}/admin/audit", headers=ctx["A"]).json())
    assert c.get(f"{API}/stock-control/damage-loss", headers=ctx["C"]).status_code == 403


def test_internal_use_is_its_own_type_and_counts_as_loss(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    item = _new_item(ctx)
    _purchase(ctx, item["item_id"], 5, 40)
    r = c.post(f"{API}/stock-control/damage-loss", params={"admin_password": PASSWORD_ADMIN}, headers=ctx["A"],
               json={"item_id": item["item_id"], "quantity": "1", "reason": "used in shop", "loss_type": "INTERNAL_USE"})
    assert r.status_code == 200, r.text
    row = next(x for x in c.get(f"{API}/stock-control/damage-loss", headers=ctx["A"]).json() if x["damage_loss_id"] == r.json()["damage_loss_id"])
    assert row["loss_type"] == "INTERNAL_USE" and row["review_status"] == "APPROVED"
    assert c.post(f"{API}/stock-control/damage-loss", params={"admin_password": PASSWORD_ADMIN}, headers=ctx["A"],
                  json={"item_id": item["item_id"], "quantity": "1", "reason": "x", "loss_type": "BOGUS"}).status_code == 422


def test_cashier_marked_return_damage_is_pending_until_admin_finalizes_or_restocks(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    item = _new_item(ctx)
    _purchase(ctx, item["item_id"], 5, 100)
    from tests.test_e2e_requirements import _sale
    sale = _sale(ctx, ctx["C"], item["item_id"], 300).json()
    line_id = c.get(f"{API}/sales/{sale['sale_id']}", headers=ctx["C"]).json()["lines"][0]["sale_line_id"]
    ret = c.post(f"{API}/returns", headers=ctx["C"], json={"original_sale_id": sale["sale_id"], "reason": "broken",
                 "lines": [{"sale_line_id": line_id, "quantity": "1", "condition": "DAMAGED"}], "return_charge": "0", "idempotency_key": uuid.uuid4().hex})
    assert ret.status_code == 200, ret.text
    recs = [x for x in c.get(f"{API}/stock-control/damage-loss", headers=ctx["A"]).json() if x["source_type"] == "RETURN" and x["item_code"] == item["item_code"]]
    assert len(recs) == 1 and recs[0]["review_status"] == "PENDING"
    did = recs[0]["damage_loss_id"]
    fin = f"{API}/stock-control/damage-loss/{did}/finalize"
    assert c.post(fin, params={"admin_password": PASSWORD_ADMIN}, headers=ctx["C"]).status_code == 403
    assert c.post(fin, params={"admin_password": PASSWORD_ADMIN}, headers=ctx["A"]).json()["review_status"] == "APPROVED"
    assert c.post(fin, params={"admin_password": PASSWORD_ADMIN}, headers=ctx["A"]).status_code == 400
    assert any(a["action_type"] == "DAMAGE_FINALIZED" for a in c.get(f"{API}/admin/audit", headers=ctx["A"]).json())
