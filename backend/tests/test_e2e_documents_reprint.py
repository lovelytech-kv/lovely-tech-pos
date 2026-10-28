"""Requirements 02: a cashier can search/reprint their OWN completed sales; settlement proofs stay Admin-only."""
import pytest

from tests.test_e2e_requirements import _db_available, _ensure_day, _new_item, _sale, ctx  # noqa: F401

pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")


def test_cashier_reprints_own_sale_but_not_admin_sale_or_settlement(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    item = _new_item(ctx)
    mine = _sale(ctx, ctx["C"], item["item_id"], 500).json()
    theirs = _sale(ctx, ctx["A"], item["item_id"], 500).json()

    found = c.get(f"/api/v1/documents/search?q={mine['invoice_no']}", headers=ctx["C"])
    assert found.status_code == 200 and [x["document_no"] for x in found.json()] == [mine["invoice_no"]]
    assert c.get(f"/api/v1/documents/search?q={theirs['invoice_no']}", headers=ctx["C"]).json() == []   # not their sale
    assert c.get(f"/api/v1/documents/search?q={theirs['invoice_no']}", headers=ctx["A"]).json()          # Admin sees all

    ok = c.post(f"/api/v1/documents/SALE/{mine['sale_id']}/reprint", headers=ctx["C"])
    assert ok.status_code == 200 and ok.json()["event_type"] == "REPRINT"
    assert c.post(f"/api/v1/documents/SALE/{theirs['sale_id']}/reprint", headers=ctx["C"]).status_code == 403
    assert c.post(f"/api/v1/documents/SETTLEMENT/{mine['sale_id']}/reprint", headers=ctx["C"]).status_code == 403
