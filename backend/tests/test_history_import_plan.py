"""scripts/history_import.py: reading the old workbooks into an ordered plan (no server needed)."""
import datetime as dt
import importlib.util
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")
SCRIPT = Path(__file__).parents[2] / "scripts" / "history_import.py"


def _mod():
    spec = importlib.util.spec_from_file_location("history_import", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _book(path, sheets):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    wb.save(path)


def test_inventory_workbook_becomes_dated_ordered_plan(tmp_path):
    d = dt.datetime
    _book(tmp_path / "inv.xlsx", {
        "Accessories Data": [["ITEM CODE", "DESCRIPTION", "Brand", "CATEGORY 1", "WARRANTY", "SALE PRICE"],
                             ["LVT0001", "CHARGER", None, "CHARGER & CABLE", "3 MONTH", 950]],
        "Purchases": [["DATE", "DESCRIPTION", "UNIT PRICE", "QUANTITY", "ITEM CODE"],
                      [d(2025, 1, 5), "CHARGER", 375, 3, "LVT0001"]],
        "Sales": [["DATE", "DESCRIPTION", "SALE PRICE", "QUANTITY", "TOTAL PRICE", "ITEM CODE"],
                  [d(2025, 1, 5), "CHARGER", 950, 2, 1900, "LVT0001"],
                  [d(2025, 1, 6), "CHARGER", 950, 1, 950, 0]],        # bad code -> matched by description
        "Dmg or Rtn": [["DATE", "DESCRIPTION", "QUANTITY", "REASON"], [d(2025, 1, 7), "CHARGER", 1, "DMG"]],
        "Phone": [["PURCHASES DATE", "DESCRIPTION", "PURCHASES PRICE", "IMEI", "SALE DATE", "SALE PRICE", "SALE"],
                  [d(2025, 1, 9), "SEALOVE PHONE", 2990, None, d(2025, 1, 8), 3900, True]],   # sold before bought
        "Online Order": [["DATE", "NAME", "TP"], [d(2025, 1, 5), "A B", "778594607"]],
    })
    m = _mod()
    p = m.build_plan(str(tmp_path / "inv.xlsx"), None)
    kinds = [(e["date"].isoformat(), e["kind"]) for e in p.events]
    assert kinds[:2] == [("2025-01-05", "purchase"), ("2025-01-05", "sale")]      # purchases before sales on the same day
    assert ("2025-01-07", "damage") in kinds
    assert sum(1 for e in p.events if e["kind"] == "sale") == 3
    assert any("matched 'CHARGER' -> LVT0001" in x for x in p.issues)
    phone_buy = next(e for e in p.events if e["ref"].startswith("INV-PH") and e["kind"] == "purchase")
    assert phone_buy["date"] == dt.date(2025, 1, 8)                                 # purchase date moved to the sale date
    assert p.customers["778594607"]["phone"] == "0778594607"
    assert p.items[("A", "LVT0001")]["warranty"] == ("MONTHS", 3)
