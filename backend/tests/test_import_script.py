"""scripts/import_data.py against the real API (TestClient): validation, opening stock + FIFO cost, IMEI, safe re-run."""
import importlib.util
import sys
import uuid
from pathlib import Path

import pytest

from tests.test_e2e_requirements import PASSWORD_ADMIN, _db_available, ctx  # noqa: F401

pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")
SCRIPT = Path(__file__).parents[2] / "scripts" / "import_data.py"


@pytest.fixture()
def run(ctx, monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("import_data", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    c = ctx["c"]

    def call(self, method, path, body=None):
        r = c.request(method, "/api/v1" + path, json=body, headers={"Authorization": f"Bearer {self.token}"} if self.token else {})
        return r.status_code, (r.json() if r.content else None)

    monkeypatch.setattr(mod.Api, "call", call)
    monkeypatch.setenv("IMPORT_ADMIN_PASSWORD", PASSWORD_ADMIN)
    monkeypatch.chdir(tmp_path)  # the report CSV is written to the current directory

    def go(items=None, customers=None, commit=True):
        argv = ["import_data.py", "--api", "http://x/api/v1", "--user", ctx["admin_user"]]
        if items:
            p = tmp_path / "items.csv"; p.write_text(items); argv += ["--items", str(p)]
        if customers:
            p = tmp_path / "cust.csv"; p.write_text(customers); argv += ["--customers", str(p)]
        if commit:
            argv.append("--commit")
        monkeypatch.setattr(sys, "argv", argv)
        return mod.main()

    return go


def test_validation_blocks_the_whole_file_and_writes_nothing(ctx, run):
    s = uuid.uuid4().hex[:6]
    bad = f"description,category,item_type,opening_qty,unit_cost,serials\nBad {s},Phones{s},Phone,2,100,111\nNo cost {s},Acc{s},Cable,5,,\n"
    assert run(items=bad) == 1
    rows = ctx["c"].get(f"/api/v1/items/admin-list?q=Bad {s}", headers=ctx["A"]).json()
    assert rows == []


def test_import_creates_stock_cost_imei_and_is_safe_to_rerun(ctx, run):
    s = uuid.uuid4().hex[:8].upper()
    items = (f"item_code,description,category,item_type,sale_price,opening_qty,unit_cost,serials\n"
             f",Imp Cable {s},Acc{s},Cable,500,20,200,\n"
             f"IMP{s},Imp Phone {s},Ph{s},Phone,30000,2,24000,{s}A;{s}B\n")
    cust = f"name,contact_no\nCust {s},077{s[:7]}\n"
    assert run(items=items, customers=cust) == 0
    stock = {x["description"]: x["stock"] for x in ctx["c"].get("/api/v1/inventory/summary", headers=ctx["A"]).json()}
    assert float(stock[f"Imp Cable {s}"]) == 20 and float(stock[f"Imp Phone {s}"]) == 2
    assert not [x for x in ctx["c"].get("/api/v1/purchases/pending-costs", headers=ctx["A"]).json() if s in str(x)]
    units = ctx["c"].get(f"/api/v1/inventory/serialized/search?q={s}&status=IN_STOCK", headers=ctx["A"]).json()
    assert {u["serial_number"] for u in units} == {f"{s}A", f"{s}B"}
    # Re-running the same files changes nothing.
    assert run(items=items, customers=cust) == 0
    stock2 = {x["description"]: x["stock"] for x in ctx["c"].get("/api/v1/inventory/summary", headers=ctx["A"]).json()}
    assert float(stock2[f"Imp Cable {s}"]) == 20
    assert len(ctx["c"].get(f"/api/v1/items/admin-list?q=Imp Cable {s}", headers=ctx["A"]).json()) == 1
