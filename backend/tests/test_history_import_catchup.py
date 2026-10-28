"""Catch-up imports: the shop keeps working in Excel until go-live, so the history import is re-run with newer
workbooks. It must add only the new rows (even when rows are inserted/sorted), honour a cut-over date, and
detect edited old rows."""
import datetime as dt
import importlib.util
import sys
import uuid
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")
from tests.test_e2e_requirements import PASSWORD_ADMIN, _db_available, ctx  # noqa: F401,E402

pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")
SCRIPT = Path(__file__).parents[2] / "scripts" / "history_import.py"
d = dt.datetime


@pytest.fixture()
def run(ctx, monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("history_import", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def call(self, method, path, body=None):
        r = ctx["c"].request(method, "/api/v1" + path, json=body, headers={"Authorization": f"Bearer {self.token}"} if self.token else {})
        return r.status_code, (r.json() if r.content else None)

    monkeypatch.setattr(mod.Api, "call", call)
    monkeypatch.setenv("IMPORT_ADMIN_PASSWORD", PASSWORD_ADMIN)

    def runner(book, *extra):
        monkeypatch.setattr(sys, "argv", ["history_import.py", "--api", "http://x/api/v1", "--user", ctx["admin_user"],
                                          "--inventory", str(book), "--report", str(tmp_path / "rep.csv"), *extra])
        return mod.main()

    return runner


def _book(path, code, name, purchases, sales, base=dt.datetime(2019, 3, 1)):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for sheet, rows in {
        "Accessories Data": [["ITEM CODE", "DESCRIPTION", "Brand", "CATEGORY 1", "WARRANTY", "SALE PRICE"], [code, name, None, "HISTCAT", "3 MONTH", 900]],
        "Purchases": [["DATE", "DESCRIPTION", "UNIT PRICE", "QUANTITY", "ITEM CODE"]] + [[base + dt.timedelta(days=o), name, c, q, code] for o, q, c in purchases],
        "Sales": [["DATE", "DESCRIPTION", "SALE PRICE", "QUANTITY", "TOTAL PRICE", "ITEM CODE"]] + [[base + dt.timedelta(days=o), name, p, q, p * q, code] for o, q, p in sales],
        "Dmg or Rtn": [["DATE", "DESCRIPTION", "QUANTITY", "REASON"]],
        "Phone": [["PURCHASES DATE", "DESCRIPTION", "PURCHASES PRICE", "IMEI", "SALE DATE", "SALE PRICE", "SALE"]],
        "Online Order": [["DATE", "NAME", "TP"]],
    }.items():
        ws = wb.create_sheet(sheet)
        for r in rows:
            ws.append(r)
    wb.save(path)


def _stock(ctx, name):
    rows = ctx["c"].get("/api/v1/inventory/summary", headers=ctx["A"]).json()
    return float(next(x["stock"] for x in rows if x["description"] == name))


def _sales_total(ctx, a, b):
    r = ctx["c"].post("/api/v1/reports/sales-summary", headers=ctx["A"], json={"start": a, "end": b})
    return float(r.json()["sales_total"])


def test_rerun_with_newer_workbook_adds_only_new_rows(ctx, run, tmp_path):
    code, name = f"LVT{uuid.uuid4().int % 9000 + 1000}", f"HIST ITEM {uuid.uuid4().hex[:6].upper()}"
    book = tmp_path / "w.xlsx"
    _book(book, code, name, purchases=[(0, 10, 100), (1, 5, 100)], sales=[(2, 2, 900), (2, 2, 900)])    # two identical sales rows
    assert run(book, "--commit") == 0
    assert _stock(ctx, name) == 15 - 4 and _sales_total(ctx, "2019-03-03", "2019-03-03") == 3600

    # Newer workbook: a row inserted in the MIDDLE of the sheet (row numbers shift) + new later rows.
    _book(book, code, name, purchases=[(0, 10, 100), (1, 5, 100), (3, 4, 120)], sales=[(2, 2, 900), (1, 1, 900), (2, 2, 900), (5, 1, 950)])
    assert run(book, "--commit") == 0
    assert _stock(ctx, name) == 19 - 6                                  # +4 bought, +2 sold; nothing duplicated
    assert _sales_total(ctx, "2019-03-01", "2019-03-31") == 3600 + 900 + 950

    # A third run with nothing new changes nothing and verifies clean.
    assert run(book, "--commit", "--since", "2019-03-02") == 0
    assert _stock(ctx, name) == 13


def test_cutover_date_blocks_later_records_and_verify_detects_edits(ctx, run, tmp_path, capsys):
    code, name = f"LVT{uuid.uuid4().int % 9000 + 1000}", f"HIST ITEM {uuid.uuid4().hex[:6].upper()}"
    book = tmp_path / "w.xlsx"
    _book(book, code, name, purchases=[(0, 10, 100)], sales=[(1, 1, 900), (9, 1, 900)], base=dt.datetime(2018, 5, 1))
    assert run(book, "--commit", "--until", "2018-05-05") == 0
    assert _stock(ctx, name) == 9                                         # the sale after the cut-over day was NOT imported
    assert run(book, "--verify-only", "--until", "2018-05-05") == 0

    # The owner corrects an already imported sale price in Excel: it looks like a new row, so verify must flag the month.
    _book(book, code, name, purchases=[(0, 10, 100)], sales=[(1, 1, 950), (9, 1, 900)], base=dt.datetime(2018, 5, 1))
    assert run(book, "--commit", "--until", "2018-05-05") == 1
    assert "DIFFERENT 2018-05" in capsys.readouterr().out
