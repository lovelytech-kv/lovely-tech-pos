#!/usr/bin/env python3
"""Lovely Tech POS - one-time import of the old Excel history (Inventory_Management + Repair_Management workbooks).

Loads two years of purchases, sales, damage/loss, repairs and expenses with their REAL dates, in date order
(purchases before sales on the same day), through the normal Admin API, so FIFO cost, stock, warranties and every
report (monthly sales / profit / repair income) are rebuilt by the system itself.

  pip install openpyxl
  python scripts/history_import.py --api http://SERVER:8000/api/v1 --user admin \
      --inventory Inventory_Management_Lovely_Tech.xlsx --repair Repair_Management_Lovely_Tech.xlsx
        (default = DRY RUN: reads the files, checks everything, prints the plan; add --commit to write)
  Admin password: env IMPORT_ADMIN_PASSWORD or prompt.

Safe to re-run after an interruption: every record carries a fixed idempotency key / reference (HIST-...), so
already imported rows are skipped. Run it on an EMPTY shop database (before real daily use starts), after a backup.
See docs/HISTORY_IMPORT.md for how each sheet is mapped.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import getpass
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP

import warnings

warnings.filterwarnings("ignore")

CENT = Decimal("0.01")
UNCAT = "UNCATEGORIZED"


# ----------------------------------------------------------------------------- helpers
def N(v) -> str:
    """Normalise text for matching: trim, collapse spaces, upper-case, 8.0 -> '8'."""
    if v is None:
        return ""
    if isinstance(v, float) and v == int(v):
        v = int(v)
    return re.sub(r"\s+", " ", str(v)).strip().upper()


def D(v) -> Decimal:
    return Decimal(str(v if v is not None else 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def isdate(v) -> bool:
    return isinstance(v, dt.datetime)


def table(ws):
    rows = list(ws.iter_rows(values_only=True))
    hdr = [(h or "").strip() if isinstance(h, str) else (h or "") for h in rows[0]]
    for n, r in enumerate(rows[1:], start=2):
        yield n, {hdr[j]: r[j] for j in range(len(hdr)) if hdr[j]}


WARRANTY = {  # sheet text -> (type, duration)
    "1 MONTH": ("MONTHS", 1), "2 WEEKS": ("DAYS", 14), "3 MONTH": ("MONTHS", 3), "6 MONTH": ("MONTHS", 6),
    "12 MONTH": ("MONTHS", 12), "36 MONTH": ("MONTHS", 36), "CHECKING ONLY": ("CHECKING ONLY", None),
    "NO WARRNTY": ("NONE", None), "NO": ("NONE", None),
}


class Plan:
    def __init__(self):
        self.items: dict[tuple, dict] = {}      # key -> item spec
        self.events: list[dict] = []            # dated records, executed in order
        self.issues: list[str] = []
        self.skipped: list[str] = []
        self.customers: dict[str, dict] = {}    # phone -> {name, phone}
        self._seen = Counter()

    def ref(self, prefix, *fields):
        """Stable id of a sheet row from its CONTENT (not its row number): re-running with newer files, sorted or
        with rows inserted, never imports the same row twice. Identical rows on the same day get 1, 2, 3 ..."""
        base = f"{prefix}-{_h(prefix, *fields)}"
        self._seen[base] += 1
        return f"{base}-{self._seen[base]}"

    def item(self, key, **spec):
        self.items.setdefault(key, {"key": key, "price": None, "brand": None, "model": None, "warranty": None, **spec})
        return self.items[key]

    def ev(self, kind, date, key=None, **kw):
        self.events.append({"kind": kind, "date": date, "item": key, **kw})


def _h(*fields) -> str:
    return hashlib.sha1("|".join(str(f) for f in fields).encode()).hexdigest()[:12]


PRIORITY = {"purchase": 0, "sale": 1, "damage": 2, "repair": 3, "expense": 4}


def build_plan(inv_path: str | None, rep_path: str | None) -> Plan:
    import openpyxl
    p = Plan()
    next_code = {"phone": 6001, "display": 7001, "pc": 8001}

    # ------------------------------------------------------------------ inventory workbook
    if inv_path:
        wb = openpyxl.load_workbook(inv_path, data_only=True)
        desc2code = {}
        for n, r in table(wb["Accessories Data"]):
            code = N(r.get("ITEM CODE"))
            if not code:
                continue
            w = WARRANTY.get(N(r.get("WARRANTY")))
            p.item(("A", code), code=code, description=str(r["DESCRIPTION"]).strip(), category=N(r.get("CATEGORY 1")) or UNCAT,
                   type="Accessory", brand=str(r.get("Brand")).strip() if r.get("Brand") else None, price=D(r["SALE PRICE"]) if r.get("SALE PRICE") else None,
                   warranty=w)
            desc2code.setdefault(N(r["DESCRIPTION"]), code)

        def acode(r, where, n):
            c = N(r.get("ITEM CODE"))
            if ("A", c) in p.items:
                return c
            c2 = desc2code.get(N(r.get("DESCRIPTION")))
            if c2:
                p.issues.append(f"Inventory/{where} row {n}: item code '{c}' is not in Accessories Data; matched '{r.get('DESCRIPTION')}' -> {c2}")
                return c2
            p.issues.append(f"Inventory/{where} row {n}: cannot match item '{r.get('DESCRIPTION')}' (code '{c}') - row skipped")
            return None

        for n, r in table(wb["Purchases"]):
            if not isdate(r["DATE"]):
                continue
            c = acode(r, "Purchases", n)
            if c:
                p.ev("purchase", r["DATE"].date(), ("A", c), qty=D(r["QUANTITY"]), cost=D(r["UNIT PRICE"]), ref=p.ref("INV-P", r["DATE"].date(), c, D(r["QUANTITY"]), D(r["UNIT PRICE"])))
        for n, r in table(wb["Sales"]):
            if not isdate(r["DATE"]):
                continue
            c = acode(r, "Sales", n)
            if c:
                if abs(D(r["TOTAL PRICE"]) - D(r["QUANTITY"]) * D(r["SALE PRICE"])) > Decimal("0.5"):
                    p.issues.append(f"Inventory/Sales row {n}: TOTAL PRICE {r['TOTAL PRICE']} differs from price x qty; price x qty used")
                p.ev("sale", r["DATE"].date(), ("A", c), qty=D(r["QUANTITY"]), price=D(r["SALE PRICE"]), ref=p.ref("INV-S", r["DATE"].date(), c, D(r["QUANTITY"]), D(r["SALE PRICE"])))
        for n, r in table(wb["Dmg or Rtn"]):
            if not isdate(r["DATE"]):
                continue
            c = desc2code.get(N(r["DESCRIPTION"]))
            if not c:
                p.issues.append(f"Inventory/Dmg or Rtn row {n}: item '{r['DESCRIPTION']}' not found - skipped")
                continue
            p.ev("damage", r["DATE"].date(), ("A", c), qty=D(r["QUANTITY"]), reason=f"{N(r['REASON']) or 'DMG'} (old sheet)", ref=p.ref("INV-D", r["DATE"].date(), c, D(r["QUANTITY"]), N(r["REASON"])))
        # phones (no IMEI recorded in the sheet: tracked as plain stock items)
        for n, r in table(wb["Phone"]):
            if not isdate(r["PURCHASES DATE"]):
                continue
            key = ("PH", N(r["DESCRIPTION"]))
            if key not in p.items:
                p.item(key, code=f"LVT{next_code['phone']}", description=str(r["DESCRIPTION"]).strip(), category="PHONES", type="Phone (old stock)")
                next_code["phone"] += 1
            pdate = r["PURCHASES DATE"].date()
            sdate = r["SALE DATE"].date() if isdate(r["SALE DATE"]) else None
            buy_ref = p.ref("INV-PH", pdate, key[1], D(r["PURCHASES PRICE"]))      # purchase side only: a later sale does not change it
            if r["SALE"] is True and sdate and sdate < pdate:
                p.issues.append(f"Inventory/Phone row {n}: sold before purchased; purchase date moved to {sdate}")
                pdate = sdate
            p.ev("purchase", pdate, key, qty=D(1), cost=D(r["PURCHASES PRICE"]), ref=buy_ref)
            if r["SALE"] is True and sdate:
                p.ev("sale", sdate, key, qty=D(1), price=D(r["SALE PRICE"]), ref=p.ref("INV-PHS", sdate, key[1], D(r["SALE PRICE"])))
        for n, r in table(wb["Online Order"]):  # customer directory only: the sales themselves are already in the Sales sheet
            tp = re.sub(r"\D", "", str(r.get("TP") or ""))
            if isdate(r["DATE"]) and r.get("NAME") and tp:
                p.customers.setdefault(tp, {"name": str(r["NAME"]).strip(), "phone": tp if tp.startswith("0") else "0" + tp})

    # ------------------------------------------------------------------ repair workbook
    if rep_path:
        wb = openpyxl.load_workbook(rep_path, data_only=True)
        pkey = {}
        for n, r in table(wb["Part Data"]):
            code = N(r.get("ITEM CODE"))
            if not code:
                continue
            w = None
            p.item(("P", code), code=code, description=str(r["DESCRIPTION"]).strip(), category=N(r.get("CATEGORY")) or UNCAT, type="Repair part",
                   brand=str(r["BRAND"]).strip() if r.get("BRAND") else None, model=N(r.get("MODLE")) or None, price=D(r["SALE PRICE"]) if r.get("SALE PRICE") else None, warranty=w)
            pkey.setdefault((N(r["DESCRIPTION"]), N(r.get("BRAND")), N(r.get("MODLE")), N(r.get("CATEGORY"))), code)
        pdesc = defaultdict(set)
        for (d, b, m, c), code in pkey.items():
            pdesc[d].add(code)

        def pcode(r, where, n):
            k = (N(r["DESCRIPTION"]), N(r.get("BRAND")), N(r.get("MODLE")), N(r.get("CATEGORY")))
            if k in pkey:
                return pkey[k]
            if len(pdesc.get(k[0], ())) == 1:
                return next(iter(pdesc[k[0]]))
            p.issues.append(f"Repair/{where} row {n}: cannot match part '{r['DESCRIPTION']}' - row skipped")
            return None

        for n, r in table(wb["Purchases"]):
            if isdate(r["DATE"]):
                c = pcode(r, "Purchases", n)
                if c:
                    p.ev("purchase", r["DATE"].date(), ("P", c), qty=D(r["QUANTITY"]), cost=D(r["UNIT PRICE"]), ref=p.ref("REP-P", r["DATE"].date(), c, D(r["QUANTITY"]), D(r["UNIT PRICE"])))
        for n, r in table(wb["Sales"]):
            if isdate(r["DATE"]):
                c = pcode(r, "Sales", n)
                if c:
                    p.ev("sale", r["DATE"].date(), ("P", c), qty=D(r["QUANTITY"]), price=D(r["SALE PRICE"]), ref=p.ref("REP-S", r["DATE"].date(), c, D(r["QUANTITY"]), D(r["SALE PRICE"])))
        for n, r in table(wb["Dmg or Rtn"]):
            if isdate(r["DATE"]):
                p.issues.append(f"Repair/Dmg or Rtn row {n}: not imported (sheet is expected to be empty)")
        # display units and PC / laptop items: one row = one unit bought, sold later
        for sheet, tag, cat_of in (("Display", "D", lambda r: "DISPLAY"), ("PC", "C", lambda r: N(r.get("CATEGORY")) or "PC")):
            for n, r in table(wb[sheet]):
                if not isdate(r["DATE"]):
                    continue
                if tag == "D":
                    desc = f"DISPLAY {N(r.get('BRAND'))} {N(r.get('MODLE'))} {N(r['DESCRIPTION'])}".replace("  ", " ").strip()
                    key = ("D", N(r.get("BRAND")), N(r.get("MODLE")), N(r["DESCRIPTION"]))
                    kind, cost = "display", r["PURCHASE PRICE"]
                    brand, model = (str(r["BRAND"]).strip() if r.get("BRAND") else None), (N(r.get("MODLE")) or None)
                else:
                    desc = str(r["DESCRIPTION"]).strip()
                    key = ("C", N(r.get("CATEGORY")), N(r["DESCRIPTION"]))
                    kind, cost = "pc", r["COST"]
                    brand = model = None
                if key not in p.items:
                    p.item(key, code=f"LVT{next_code[kind]}", description=desc, category=cat_of(r), type="Display" if tag == "D" else "PC / laptop", brand=brand, model=model)
                    next_code[kind] += 1
                pdate = r["DATE"].date()
                sdate = r["SALE DATE"].date() if isdate(r["SALE DATE"]) else None
                buy_ref = p.ref(f"REP-{tag}", pdate, key, D(cost))
                if r["SALE"] is True and sdate and sdate < pdate:
                    p.issues.append(f"Repair/{sheet} row {n}: sold before purchased; purchase date moved to {sdate}")
                    pdate = sdate
                p.ev("purchase", pdate, key, qty=D(1), cost=D(cost), ref=buy_ref)
                if r["SALE"] is True and sdate:
                    p.ev("sale", sdate, key, qty=D(1), price=D(r["SALE PRICE"]), ref=p.ref(f"REP-{tag}S", sdate, key, D(r["SALE PRICE"])))
        p.item(("X", "REPAIRCOST"), code="HIST-REPAIR-COST", description="HISTORICAL REPAIR PARTS COST (no stock)", category="SERVICE", type="Repair part")
        for n, r in table(wb["Other Repair"]):
            if not isdate(r["DATE"]):
                continue
            if not r["SALE PRICE"] and not r["COST"]:
                p.skipped.append(f"Repair/Other Repair row {n}: price and cost are both 0 - skipped")
                continue
            p.ev("repair", r["DATE"].date(), None, brand=str(r["BRAND"]).strip() if r.get("BRAND") else None, model=N(r.get("MODLE")) or None,
                 description=f"{str(r['DESCRIPTION']).strip()} [{N(r.get('CATEGORY'))}]", price=D(r["SALE PRICE"]), cost=D(r["COST"]), ref=p.ref("HIST-OR", r["DATE"].date(), N(r.get("BRAND")), N(r.get("MODLE")), N(r["DESCRIPTION"]), D(r["SALE PRICE"]), D(r["COST"])))
        for n, r in table(wb["Other Exp"]):
            if isdate(r["DATE"]) and r["AMOUNT"]:
                p.ev("expense", r["DATE"].date(), None, amount=D(r["AMOUNT"]), description=str(r["DESCRIPTION"]).strip(), ref=p.ref("HIST-EXP", r["DATE"].date(), N(r["DESCRIPTION"]), D(r["AMOUNT"])))

    # last sale price becomes the item's list price when the sheet has none
    last = {}
    for e in sorted((x for x in p.events if x["kind"] == "sale"), key=lambda x: x["date"]):
        last[e["item"]] = e["price"]
    for k, spec in p.items.items():
        if spec["price"] is None and k in last:
            spec["price"] = last[k]
    codes = Counter(s["code"] for s in p.items.values())
    for c, v in codes.items():
        if v > 1:
            p.issues.append(f"item code {c} is used {v} times")
    p.events.sort(key=lambda e: (e["date"], PRIORITY[e["kind"]]))
    return p


# ----------------------------------------------------------------------------- API
class Api:
    def __init__(self, base):
        self.base, self.token = base.rstrip("/"), None

    def call(self, method, path, body=None):
        req = urllib.request.Request(self.base + path, method=method, data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, {"detail": raw[:300].decode(errors="ignore")}
        except urllib.error.URLError as e:
            sys.exit(f"Cannot reach the POS server at {self.base}: {e.reason}")


def summarise(p: Plan):
    c = Counter(e["kind"] for e in p.events)
    print(f"Items to create: {len(p.items)}   Customers: {len(p.customers)}")
    print("Records:", ", ".join(f"{k}={v}" for k, v in sorted(c.items())))
    dates = [e["date"] for e in p.events]
    print(f"Date range: {min(dates)} .. {max(dates)}")
    sales = sum(e["qty"] * e["price"] for e in p.events if e["kind"] == "sale")
    buys = sum(e["qty"] * e["cost"] for e in p.events if e["kind"] == "purchase")
    reps = sum(e["price"] for e in p.events if e["kind"] == "repair")
    print(f"Sales Rs. {sales:,.2f}   Purchases Rs. {buys:,.2f}   Repair income Rs. {reps:,.2f}")
    print(f"{len(p.issues)} data note(s), {len(p.skipped)} skipped row(s)")


def verify(api, events, until=None) -> int:
    """Month by month: sales, repair income and expenses in the POS must equal the workbooks. Catches edited or
    deleted old rows (an edited row looks like a new one) and any failed record. Returns the number of differing months."""
    import calendar
    want = defaultdict(lambda: {"sales": Decimal(0), "repair": Decimal(0), "exp": Decimal(0)})
    for e in events:
        m = e["date"].strftime("%Y-%m")
        if e["kind"] == "sale":
            want[m]["sales"] += (e["qty"] * e["price"]).quantize(CENT, rounding=ROUND_HALF_UP)
        elif e["kind"] == "repair":
            want[m]["repair"] += e["price"]
        elif e["kind"] == "expense":
            want[m]["exp"] += e["amount"]
    bad = 0
    for m in sorted(want):
        y, mo = int(m[:4]), int(m[5:])
        end = dt.date(y, mo, calendar.monthrange(y, mo)[1])
        if until and until < end:
            end = until
        s, r = api.call("POST", "/reports/sales-summary", {"start": f"{m}-01", "end": end.isoformat()})
        if s != 200:
            print("  verify failed:", m, r)
            return 1
        got = {"sales": Decimal(str(r["sales_total"])), "repair": Decimal(str(r["repair_income"])), "exp": Decimal(str(r["expenses_total"]))}
        diff = {k: got[k] - want[m][k] for k in got if abs(got[k] - want[m][k]) > Decimal("0.5")}
        if diff:
            bad += 1
            print(f"  DIFFERENT {m}: " + ", ".join(f"{k} system {got[k]:,.2f} vs sheet {want[m][k]:,.2f}" for k in diff))
    print(f"Verified {len(want)} month(s): {'ALL MATCH' if not bad else str(bad) + ' month(s) differ - see above'}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", required=True)
    ap.add_argument("--user", default="admin")
    ap.add_argument("--inventory")
    ap.add_argument("--repair")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--since", help="YYYY-MM-DD: only process records on/after this date (fast catch-up run; overlap with earlier runs is harmless)")
    ap.add_argument("--until", help="YYYY-MM-DD: cut-over date: never import records after this day (the POS takes over from the next day)")
    ap.add_argument("--verify-only", action="store_true", help="write nothing; compare the system's monthly sales / repair income / expenses with the workbooks")
    ap.add_argument("--report", default="history-import-report.csv")
    a = ap.parse_args()
    if not a.inventory and not a.repair:
        ap.error("give --inventory and/or --repair")
    plan = build_plan(a.inventory, a.repair)
    since = dt.date.fromisoformat(a.since) if a.since else None
    until = dt.date.fromisoformat(a.until) if a.until else None
    all_events = [e for e in plan.events if not until or e["date"] <= until]   # what the system must contain after the import
    if since or until:
        before = len(plan.events)
        plan.events = [e for e in plan.events if (not since or e["date"] >= since) and (not until or e["date"] <= until)]
        print(f"Date filter: {before - len(plan.events)} record(s) outside {since or '...'} .. {until or '...'} left out")
    summarise(plan)
    for m in plan.issues[:40]:
        print("  note:", m)
    if not a.commit and not a.verify_only:
        print("\nDry run only - nothing written. Re-run with --commit to import.")
        return 0
    pw = os.environ.get("IMPORT_ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    api = Api(a.api)
    s, r = api.call("POST", "/auth/login", {"username": a.user, "password": pw})
    if s != 200:
        print("Login failed:", r.get("detail"))
        return 2
    api.token = r["access_token"]
    pwq = "admin_password=" + urllib.parse.quote(pw, safe="")
    out, fails = [], 0
    if a.verify_only:
        return verify(api, all_events, until)

    def note(ref, result):
        nonlocal fails
        out.append((ref, result))
        if result.startswith("FAILED"):
            fails += 1
            if fails <= 25:
                print("  !", ref, result)

    # ---- masters
    s, masters = api.call("GET", "/items/masters")
    cats = {c["name"].upper(): c["id"] for c in masters["categories"]}
    types = {t["name"].upper(): t["id"] for t in masters["item_types"]}
    for spec in plan.items.values():
        if spec["category"] not in cats:
            s, r = api.call("POST", "/items/categories", {"name": spec["category"]})
            if s == 409:
                s, masters = api.call("GET", "/items/masters"); cats = {c["name"].upper(): c["id"] for c in masters["categories"]}
            else:
                cats[spec["category"]] = r["id"]
        if spec["type"].upper() not in types:
            code = re.sub(r"[^A-Z0-9]", "", spec["type"].upper())[:12] or "TYPE"
            s, r = api.call("POST", "/items/item-types", {"code": code, "name": spec["type"], "is_serialized": False})
            if s != 200:
                s, masters = api.call("GET", "/items/masters"); types = {t["name"].upper(): t["id"] for t in masters["item_types"]}
            else:
                types[spec["type"].upper()] = r["id"]
    # ---- items
    ids = {}
    for i, (key, spec) in enumerate(plan.items.items(), 1):
        body = {"item_code": spec["code"], "description": spec["description"][:255], "category_id": cats[spec["category"]],
                "item_type_id": types[spec["type"].upper()], "brand": (spec["brand"] or None), "model": spec["model"],
                "master_sale_price": str(spec["price"]) if spec["price"] is not None else None}
        generated = key[0] in ("PH", "D", "C")   # codes LVT6001/7001/8001.. are handed out by this script
        hit = None
        if generated:  # same description already in the database (earlier import): reuse it, whatever code it got
            s2, found = api.call("GET", "/items/admin-list?q=" + urllib.parse.quote(spec["description"][:100]))
            hit = next((x for x in (found or []) if N(x.get("description")) == N(spec["description"])), None)
        if hit:
            ids[key] = hit["item_id"]
        else:
            for _ in range(200):
                s, r = api.call("POST", "/items", body)
                if s == 409 and generated and "code" in str(r.get("detail", "")).lower():
                    m = re.match(r"^(LVT)(\d+)$", body["item_code"])
                    body["item_code"] = f"LVT{int(m.group(2)) + 1}" if m else body["item_code"] + "X"
                    continue
                break
            if s == 200:
                ids[key] = r["item_id"]
                if spec["warranty"]:
                    wt, dur = spec["warranty"]
                    api.call("PUT", f"/items/{r['item_id']}/warranty-default", {"warranty_type": wt, "duration_value": dur})
            elif s == 409:
                s2, found = api.call("GET", "/items/admin-list?q=" + urllib.parse.quote(spec["code"]))
                hit = next((x for x in (found or []) if x["item_code"] == spec["code"]), None)
                if hit:
                    ids[key] = hit["item_id"]
                    if N(hit.get("description")) != N(spec["description"]):
                        note(f"item {spec['code']}", f"NOTE code already used by '{hit.get('description')}' (sheet says '{spec['description']}')")
                else:
                    note(f"item {spec['code']}", "FAILED item exists but cannot be read")
            else:
                note(f"item {spec['code']}", f"FAILED {s}: {r.get('detail')}")
        if i % 200 == 0:
            print(f"  items {i}/{len(plan.items)}")
    print(f"Items ready: {len(ids)}/{len(plan.items)}")

    # ---- expense category + customers
    s, ecats = api.call("GET", "/admin/expense-categories")
    ecat = next((c["id"] for c in ecats if c["name"] == "Shop expenses (old records)"), None)
    if ecat is None:
        s, r = api.call("POST", "/admin/expense-categories", {"name": "Shop expenses (old records)"})
        ecat = r["id"]
    for tp, c in plan.customers.items():
        s, found = api.call("GET", "/customers?q=" + urllib.parse.quote(c["phone"]))
        if not any(x.get("contact_no") == c["phone"] for x in (found or [])):
            s, r = api.call("POST", "/customers", {"name": c["name"], "contact_no": c["phone"], "notes": "From old Online Order sheet"})
            note(f"customer {c['phone']}", "CUSTOMER CREATED" if s == 200 else f"FAILED {s}: {r.get('detail')}")

    # ---- dated records, in order. Purchases of one day are batched (one line per item and cost).
    day_events = defaultdict(list)
    for e in plan.events:
        day_events[e["date"]].append(e)
    done = 0
    total = len(plan.events)
    for day in sorted(day_events):
        evs = day_events[day]
        # purchases: ONE purchase per sheet row, keyed by its content id, so a re-run with a newer workbook can never
        # duplicate a row or clash with a different grouping (the cost is completed right away).
        for e in (x for x in evs if x["kind"] == "purchase"):
            if e["item"] not in ids:
                note(e["ref"], "FAILED item missing")
                continue
            s, r = api.call("POST", "/purchases", {"purchase_date": day.isoformat(), "reference_no": e["ref"], "notes": "Imported old purchase",
                                                  "lines": [{"item_id": ids[e["item"]], "quantity": str(e["qty"]), "line_date": day.isoformat()}],
                                                  "idempotency_key": f"HIST-P-{e['ref']}"})
            if s != 200:
                note(e["ref"], f"FAILED {s}: {r.get('detail')}")
                continue
            s, pend = api.call("GET", "/purchases/pending-costs")
            row = next((x for x in (pend or []) if x["purchase_id"] == r["purchase_id"]), None)
            if row is None:
                note(e["ref"], "OK (already imported)")
                continue
            s, r2 = api.call("POST", "/purchases/complete-cost", {"purchase_id": row["purchase_id"], "purchase_line_id": row["purchase_line_id"],
                                                                  "unit_cost": str(e["cost"]), "version": row["version"], "purchase_version": row["purchase_version"]})
            note(e["ref"], "OK" if s == 200 else f"FAILED cost {s}: {r2.get('detail')}")
        done += sum(1 for x in evs if x["kind"] == "purchase")
        # everything else
        for e in (x for x in evs if x["kind"] != "purchase"):
            k = e["kind"]
            if k == "sale":
                if e["item"] not in ids:
                    note(e["ref"], "FAILED item missing"); continue
                amount = (e["qty"] * e["price"]).quantize(CENT, rounding=ROUND_HALF_UP)
                if amount <= 0:  # the old sheet books a Rs.0 "sale" as a loss of the unit's cost: same as a damage/loss entry
                    s, r = api.call("POST", f"/admin/history/damage-loss?{pwq}", {"item_id": ids[e["item"]], "quantity": str(e["qty"]), "occurred_on": day.isoformat(),
                                                                                  "reason": "SOLD FOR Rs.0 (old sheet)", "idempotency_key": f"HIST-Z-{e['ref']}"})
                    note(e["ref"], "OK (zero-price sale booked as loss)" if s == 200 else f"FAILED {s}: {r.get('detail')}")
                    done += 1
                    continue
                s, r = api.call("POST", "/sales", {"lines": [{"item_id": ids[e["item"]], "quantity": str(e["qty"]), "unit_price": str(e["price"]), "discount": "0", "warranty_type": "NONE"}],  # old sales: no warranty records
                                                   "payments": [{"method": "CASH", "amount": str(amount)}], "document_type": "NO_PRINT",
                                                   "sale_datetime": f"{day.isoformat()}T12:00:00+05:30", "idempotency_key": f"HIST-S-{e['ref']}"})
            elif k == "damage":
                if e["item"] not in ids:
                    note(e["ref"], "FAILED item missing"); continue
                s, r = api.call("POST", f"/admin/history/damage-loss?{pwq}", {"item_id": ids[e["item"]], "quantity": str(e["qty"]), "occurred_on": day.isoformat(),
                                                                              "reason": e["reason"], "idempotency_key": f"HIST-D-{e['ref']}"})
            elif k == "repair":
                s, r = api.call("POST", f"/admin/history/repairs?{pwq}", {"done_on": day.isoformat(), "device_brand": e["brand"], "model": e["model"],
                                                                         "description": e["description"], "final_amount": str(e["price"]), "parts_cost": str(e["cost"]),
                                                                         "history_ref": e["ref"], "cost_item_id": ids.get(("X", "REPAIRCOST"))})
            else:  # expense
                s, r = api.call("POST", "/admin/expenses", {"category_id": ecat, "expense_date": day.isoformat(), "amount": str(e["amount"]), "payment_method": "CASH",
                                                            "description": e["description"], "idempotency_key": f"HIST-E-{e['ref']}"})
            note(e["ref"], "OK" if s == 200 else f"FAILED {s}: {r.get('detail')}")
            done += 1
        if done and (done // 500) != ((done - len(evs)) // 500):
            print(f"  {done}/{total} records ({day})")

    with open(a.report, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["record", "result"])
        w.writerows(out)
        for m in plan.issues:
            w.writerow(["NOTE", m])
        for m in plan.skipped:
            w.writerow(["SKIPPED", m])
    print(f"\nFinished. {sum(1 for _, r in out if not r.startswith('FAILED'))} OK, {fails} failed. Report: {a.report}")
    print("\nChecking the system against the workbooks month by month ...")
    mism = verify(api, all_events, until)
    return 1 if (fails or mism) else 0


if __name__ == "__main__":
    sys.exit(main())
