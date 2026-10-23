"""Requirements 08/11: purchase payment method is not asked or stored; purchases never reduce the Day-End drawer."""
import uuid
from datetime import date

import pytest

from tests.test_e2e_requirements import _db_available, _ensure_day, _new_item, ctx  # noqa: F401

pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")


def _buy(ctx, item, **extra):
    return ctx["c"].post("/api/v1/purchases", headers=ctx["C"], json={
        "purchase_date": date.today().isoformat(), "idempotency_key": uuid.uuid4().hex,
        "lines": [{"item_id": item["item_id"], "quantity": "3"}], **extra})


def test_purchase_does_not_accept_or_return_a_payment_method(ctx):
    item = _new_item(ctx)
    assert _buy(ctx, item, payment_method="CARD").status_code == 422
    assert _buy(ctx, item).status_code == 200
    hist = ctx["c"].get("/api/v1/purchases/history", headers=ctx["A"]).json()
    assert hist and all("payment_method" not in row for row in hist)


def test_purchase_cost_does_not_reduce_day_end_drawer_expected_cash(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    item = _new_item(ctx)
    before = c.get("/api/v1/day/status", headers=ctx["C"]).json()["expected_cash"]
    assert _buy(ctx, item).status_code == 200
    line = [x for x in c.get("/api/v1/purchases/pending-costs", headers=ctx["A"]).json() if x["item_id"] == item["item_id"]][-1]
    r = c.post("/api/v1/purchases/complete-cost", headers=ctx["A"], json={
        "purchase_id": line["purchase_id"], "purchase_line_id": line["purchase_line_id"], "unit_cost": "1000",
        "version": line["version"], "purchase_version": line["purchase_version"]})
    assert r.status_code == 200, r.text
    assert c.get("/api/v1/day/status", headers=ctx["C"]).json()["expected_cash"] == before
