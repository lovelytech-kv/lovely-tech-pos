"""Cashier discount above the limit: request -> Admin approves (with the record version) -> sale executes once.

Regression: the approvals list had no `version` and the Admin UI sent none, so the backend always answered
409 "Approval version is required" and an Admin could never approve a discount from the screen.
"""
import uuid
from datetime import date

import pytest

from tests.test_e2e_requirements import _db_available, _ensure_day, _new_item, ctx  # noqa: F401

pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")


def _payload(item, key):
    return {"lines": [{"item_id": item["item_id"], "quantity": "1", "unit_price": "1000", "discount": "600"}],
            "payments": [{"method": "CASH", "amount": "400"}], "idempotency_key": key}


def test_discount_above_limit_needs_admin_approval_and_executes_once(ctx):
    c = ctx["c"]
    _ensure_day(ctx)
    item, key = _new_item(ctx), uuid.uuid4().hex
    blocked = c.post("/api/v1/sales", headers=ctx["C"], json=_payload(item, key))
    assert blocked.status_code == 400 and "Admin approval" in blocked.text

    req = c.post("/api/v1/sales/discount-approval", headers=ctx["C"], json=_payload(item, key))
    assert req.status_code == 200, req.text
    approval_id = req.json()["approval_id"]

    # An unapproved approval id never lets the sale through.
    assert c.post("/api/v1/sales", headers=ctx["C"], json={**_payload(item, key), "admin_discount_approval_id": approval_id}).status_code == 400

    row = next(a for a in c.get("/api/v1/admin/approvals", headers=ctx["A"]).json() if a["approval_id"] == approval_id)
    assert row["status"] == "PENDING" and isinstance(row["version"], int)

    assert c.post(f"/api/v1/approvals/{approval_id}/review", headers=ctx["C"], json={"approve": True, "version": row["version"]}).status_code == 403
    assert c.post(f"/api/v1/approvals/{approval_id}/review", headers=ctx["A"], json={"approve": True}).status_code == 409
    done = c.post(f"/api/v1/approvals/{approval_id}/review", headers=ctx["A"], json={"approve": True, "version": row["version"]})
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "APPROVED" and done.json()["executed_sale_id"]

    # The cashier's retry with the same idempotency key replays the executed sale; no duplicate invoice.
    retry = c.post("/api/v1/sales", headers=ctx["C"], json={**_payload(item, key), "admin_discount_approval_id": approval_id})
    assert retry.status_code == 200, retry.text
    assert retry.json()["sale_id"] == done.json()["executed_sale_id"] and retry.json()["replayed"] is True


def test_cashier_other_income_is_listed_for_admin_and_approved_with_its_version(ctx):
    """Regression: pending Other Income had no list endpoint, so an Admin could never approve it."""
    c = ctx["c"]
    r = c.post("/api/v1/admin/other-income", headers=ctx["C"], json={
        "income_date": date.today().isoformat(), "amount": "750", "payment_method": "CASH", "description": f"oi-{uuid.uuid4().hex[:6]}"})
    assert r.status_code == 200, r.text
    oid = r.json()["other_income_id"] if "other_income_id" in r.json() else r.json().get("id")
    assert c.get("/api/v1/admin/pending-other-income", headers=ctx["C"]).status_code == 403
    rows = c.get("/api/v1/admin/pending-other-income", headers=ctx["A"]).json()
    row = next(x for x in rows if x["other_income_id"] == oid)
    assert row["status"] == "PENDING_APPROVAL" and isinstance(row["version"], int)
    assert c.post(f"/api/v1/admin/other-income/{oid}/decision?approve=true", headers=ctx["A"]).status_code == 409
    ok = c.post(f"/api/v1/admin/other-income/{oid}/decision?approve=true&version={row['version']}", headers=ctx["A"])
    assert ok.status_code == 200, ok.text
    assert all(x["other_income_id"] != oid for x in c.get("/api/v1/admin/pending-other-income", headers=ctx["A"]).json())
