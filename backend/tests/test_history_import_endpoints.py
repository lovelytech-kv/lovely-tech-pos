"""Admin back-fill endpoints: repairs and damage/loss carry their PAST date and flow into the reports."""
import uuid
import pytest

from tests.test_e2e_requirements import PASSWORD_ADMIN, _db_available, _new_item, _purchase, ctx  # noqa: F401

pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")
PAST = "2025-02-14"


def _summary(ctx, day, headers=None):
    r = ctx["c"].post("/api/v1/reports/sales-summary", headers=headers or ctx["A"], json={"start": day, "end": day})
    assert r.status_code == 200, r.text
    return r.json()


def test_historical_repair_is_dated_idempotent_and_admin_only(ctx):
    c = ctx["c"]
    cost_item = _new_item(ctx)
    ref = f"HIST-OR-{uuid.uuid4().hex[:8]}"
    body = {"done_on": PAST, "device_brand": "OPPO", "model": "A57", "description": "BATTERY REPLACE", "final_amount": "4800",
            "parts_cost": "1850", "history_ref": ref, "cost_item_id": cost_item["item_id"]}
    assert c.post("/api/v1/admin/history/repairs", params={"admin_password": PASSWORD_ADMIN}, headers=ctx["C"], json=body).status_code in (401, 403)
    before = _summary(ctx, PAST)
    r = c.post("/api/v1/admin/history/repairs", params={"admin_password": PASSWORD_ADMIN}, headers=ctx["A"], json=body)
    assert r.status_code == 200, r.text
    assert r.json()["replayed"] is False
    again = c.post("/api/v1/admin/history/repairs", params={"admin_password": PASSWORD_ADMIN}, headers=ctx["A"], json=body).json()
    assert again["replayed"] is True and again["repair_id"] == r.json()["repair_id"]
    after = _summary(ctx, PAST)
    assert float(after["repair_income"]) - float(before["repair_income"]) == 4800
    assert float(after["repair_profit"]) - float(before["repair_profit"]) == 4800 - 1850
    # stock untouched: the cost item has no movements
    assert float(next(x for x in c.get("/api/v1/inventory/summary", headers=ctx["A"]).json() if x["item_id"] == cost_item["item_id"])["stock"]) == 0


def test_historical_damage_loss_uses_its_own_date(ctx):
    c = ctx["c"]
    item = _new_item(ctx)
    r = c.post("/api/v1/purchases", headers=ctx["C"], json={"purchase_date": "2025-02-10", "idempotency_key": uuid.uuid4().hex,
                                                           "lines": [{"item_id": item["item_id"], "quantity": "10", "line_date": "2025-02-10"}]})
    assert r.status_code == 200, r.text
    line = next(x for x in c.get("/api/v1/purchases/pending-costs", headers=ctx["A"]).json() if x["purchase_id"] == r.json()["purchase_id"])
    assert c.post("/api/v1/purchases/complete-cost", headers=ctx["A"], json={"purchase_id": line["purchase_id"], "purchase_line_id": line["purchase_line_id"],
                  "unit_cost": "100", "version": line["version"], "purchase_version": line["purchase_version"]}).status_code == 200
    before = _summary(ctx, PAST)
    body = {"item_id": item["item_id"], "quantity": "2", "occurred_on": PAST, "reason": "DMG", "idempotency_key": uuid.uuid4().hex}
    r = c.post("/api/v1/admin/history/damage-loss", params={"admin_password": PASSWORD_ADMIN}, headers=ctx["A"], json=body)
    assert r.status_code == 200, r.text
    again = c.post("/api/v1/admin/history/damage-loss", params={"admin_password": PASSWORD_ADMIN}, headers=ctx["A"], json=body)
    assert again.status_code == 200 and again.json() == r.json()  # replay, not a second loss
    after = _summary(ctx, PAST)
    assert float(after["damage_loss_total"]) - float(before["damage_loss_total"]) == 200  # 2 units x cost 100, on the PAST date
