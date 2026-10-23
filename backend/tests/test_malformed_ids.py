"""A malformed id in a URL is a clean 404, never an HTTP 500 (found by fuzzing every {id} route)."""
import pytest

from tests.test_e2e_requirements import _db_available, ctx  # noqa: F401

pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")

ROUTES = [
    ("GET", "/api/v1/repairs/abc"), ("GET", "/api/v1/repairs/abc/warranty"),
    ("GET", "/api/v1/returns/abc"), ("GET", "/api/v1/returns/abc/refund-payments"),
    ("POST", "/api/v1/backup/verify/abc"), ("GET", "/api/v1/items/abc/variants"),
    ("GET", "/api/v1/customers/abc/history"),
]


@pytest.mark.parametrize("method,path", ROUTES)
def test_malformed_id_is_not_a_server_error(ctx, method, path):
    r = ctx["c"].request(method, path, headers=ctx["A"], json={} if method == "POST" else None)
    assert r.status_code in (404, 422), (r.status_code, r.text[:200])


def test_sale_lookup_accepts_invoice_number(ctx):
    from tests.test_e2e_requirements import _ensure_day, _new_item, _sale
    _ensure_day(ctx)
    item = _new_item(ctx)
    sale = _sale(ctx, ctx["C"], item["item_id"], 500).json()
    by_invoice = ctx["c"].get(f"/api/v1/sales/{sale['invoice_no']}", headers=ctx["C"])
    assert by_invoice.status_code == 200 and by_invoice.json()["sale_id"] == sale["sale_id"]
    assert ctx["c"].get("/api/v1/sales/INV-999999999", headers=ctx["C"]).status_code == 404
