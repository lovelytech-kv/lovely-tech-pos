#!/usr/bin/env python3
"""Lovely Tech POS - bulk import of items, opening stock and customers from CSV.

Goes through the normal HTTP API as an Admin, so every business rule applies (FIFO lots, IMEI rules,
audit log, preserved item codes). Safe to re-run: items whose code already exists are skipped.

  python scripts/import_data.py --api http://SERVER:8000/api/v1 --user admin --items items.csv --customers customers.csv
  (the default is a DRY RUN that only validates; add --commit to write)  Password: env IMPORT_ADMIN_PASSWORD or prompt.

items.csv columns (header row required; only description, category, item_type are mandatory):
  item_code, description, category, item_type, brand, model, sale_price, barcode,
  opening_qty, unit_cost, serials        (serials: IMEI/serial numbers separated by ; for serialized items)
customers.csv columns: name, contact_no, notes
Categories and item types that do not exist yet are created (item types ending in the word PHONE or listed with
--serialized-types are created as IMEI-tracked). Opening stock is saved as ONE purchase per run with reference
OPENING-STOCK-<date>; its unit costs are completed immediately so FIFO profit works from day one.
"""
from __future__ import annotations

import argparse
import csv
import getpass
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation


class Api:
    def __init__(self, base: str):
        self.base, self.token = base.rstrip("/"), None

    def call(self, method, path, body=None):
        req = urllib.request.Request(self.base + path, method=method, data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.URLError as e:
            if isinstance(e, urllib.error.HTTPError):
                raw = e.read()
                try:
                    return e.code, json.loads(raw)
                except Exception:
                    return e.code, {"detail": raw[:200].decode(errors="ignore")}
            sys.exit(f"Cannot reach the POS server at {self.base}: {e.reason}. Is the server running and is the address right?")
        except urllib.error.HTTPError as e:  # pragma: no cover - kept for clarity, handled above
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, {"detail": raw[:200].decode(errors="ignore")}


def rows(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for n, r in enumerate(csv.DictReader(fh), start=2):
            yield n, {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}


def money(v, label, errors, line, allow_blank=True):
    if v == "":
        return None
    try:
        d = Decimal(v.replace(",", ""))
        if d < 0:
            raise InvalidOperation
        return d
    except InvalidOperation:
        errors.append(f"line {line}: {label} '{v}' is not a valid non-negative number")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", required=True)
    ap.add_argument("--user", default="admin")
    ap.add_argument("--items")
    ap.add_argument("--customers")
    ap.add_argument("--serialized-types", default="", help="comma separated item type names to create as IMEI-tracked")
    ap.add_argument("--commit", action="store_true", help="really write (default is a validating dry run)")
    a = ap.parse_args()
    if not a.items and not a.customers:
        ap.error("give --items and/or --customers")
    pw = os.environ.get("IMPORT_ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    api = Api(a.api)
    s, r = api.call("POST", "/auth/login", {"username": a.user, "password": pw})
    if s != 200:
        print("Login failed:", r.get("detail")); return 2
    api.token = r["access_token"]
    serial_names = {x.strip().lower() for x in a.serialized_types.split(",") if x.strip()}
    errors: list[str] = []
    report: list[tuple] = []

    s, masters = api.call("GET", "/items/masters")
    cats = {c["name"].lower(): c["id"] for c in masters["categories"]}
    types = {t["name"].lower(): t for t in masters["item_types"]}
    s, existing = api.call("GET", "/items/admin-list?q=")  # first 200 only; exact duplicates are also caught by the API (409)
    existing_codes = {x["item_code"] for x in (existing or [])}

    plan_items = []
    if a.items:
        seen_codes, seen_serials, seen_barcodes = set(), set(), set()
        for n, r in rows(a.items):
            if not r.get("description") or not r.get("category") or not r.get("item_type"):
                errors.append(f"line {n}: description, category and item_type are required"); continue
            code = r.get("item_code", "")
            if code and (code in seen_codes):
                errors.append(f"line {n}: item_code {code} appears twice in the file"); continue
            seen_codes.add(code)
            price = money(r.get("sale_price", ""), "sale_price", errors, n)
            qty = money(r.get("opening_qty", ""), "opening_qty", errors, n)
            cost = money(r.get("unit_cost", ""), "unit_cost", errors, n)
            serials = [x.strip().upper() for x in r.get("serials", "").replace("\n", ";").replace(",", ";").split(";") if x.strip()]
            tname = r["item_type"].lower()
            serialized = (types[tname]["is_serialized"] if tname in types else (tname in serial_names or tname.endswith("phone")))
            if serialized:
                if qty is not None and qty != len(serials):
                    errors.append(f"line {n}: opening_qty {qty} does not match {len(serials)} serial number(s)")
                if qty is None and serials:
                    qty = Decimal(len(serials))
                dup = [x for x in serials if x in seen_serials]
                if dup:
                    errors.append(f"line {n}: serial(s) repeated in the file: {', '.join(dup)}")
                seen_serials.update(serials)
            elif serials:
                errors.append(f"line {n}: serials given but item_type '{r['item_type']}' is not IMEI-tracked")
            if qty is not None and qty > 0 and cost is None:
                errors.append(f"line {n}: opening_qty needs unit_cost (used for FIFO profit)")
            if qty is not None and qty != qty.to_integral_value() and serialized:
                errors.append(f"line {n}: serialized items need whole quantities")
            bc = r.get("barcode", "")
            if bc:
                if bc in seen_barcodes:
                    errors.append(f"line {n}: barcode {bc} appears twice in the file")
                seen_barcodes.add(bc)
            if code and code in existing_codes:
                report.append((n, code, "SKIP (code already exists)")); continue
            if not code:  # no code to compare: an item with the same description is treated as already imported
                s_, found = api.call("GET", "/items/admin-list?q=" + urllib.parse.quote(r["description"]))
                if any((x.get("description") or "").strip().lower() == r["description"].strip().lower() for x in (found or [])):
                    report.append((n, r["description"], "SKIP (an item with this description already exists)")); continue
            plan_items.append(dict(line=n, code=code, desc=r["description"], cat=r["category"], type=r["item_type"], brand=r.get("brand") or None,
                                   model=r.get("model") or None, price=price, barcode=bc or None, qty=qty, cost=cost, serials=serials, serialized=serialized))

    plan_customers = []
    if a.customers:
        for n, r in rows(a.customers):
            if not r.get("name") and not r.get("contact_no"):
                errors.append(f"line {n} (customers): name or contact_no is required"); continue
            probe = r.get("contact_no") or r.get("name")
            s_, found = api.call("GET", "/customers?q=" + urllib.parse.quote(probe))
            same = [x for x in (found or []) if (r.get("contact_no") and x.get("contact_no") == r["contact_no"])
                    or (not r.get("contact_no") and (x.get("name") or "").lower() == r["name"].lower())]
            if same:
                report.append((n, probe, "SKIP (customer already exists)")); continue
            plan_customers.append((n, r))

    print(f"Items to create: {len(plan_items)}   Customers to create: {len(plan_customers)}   Skipped: {len(report)}")
    if errors:
        print(f"\n{len(errors)} problem(s) found - nothing was written:")
        for e in errors[:100]:
            print("  -", e)
        return 1
    if not a.commit:
        print("Dry run OK. Re-run with --commit to import."); return 0

    # ---- write ----
    for it in plan_items:
        for kind, name in (("cat", it["cat"]), ("type", it["type"])):
            if kind == "cat" and name.lower() not in cats:
                s, r = api.call("POST", "/items/categories", {"name": name}); assert s == 200, r; cats[name.lower()] = r["id"]
            if kind == "type" and name.lower() not in types:
                s, r = api.call("POST", "/items/item-types", {"code": "".join(ch for ch in name.upper() if ch.isalnum())[:12] or "TYPE", "name": name, "is_serialized": it["serialized"]})
                assert s == 200, r; types[name.lower()] = r
    created, lines = [], []
    for it in plan_items:
        body = {"description": it["desc"], "category_id": cats[it["cat"].lower()], "item_type_id": types[it["type"].lower()]["id"],
                "brand": it["brand"], "model": it["model"], "master_sale_price": str(it["price"]) if it["price"] is not None else None,
                "barcode": it["barcode"]}
        if it["code"]:
            body["item_code"] = it["code"]
        s, r = api.call("POST", "/items", body)
        if s == 409:  # already imported earlier: re-running the same file is safe
            report.append((it["line"], it["code"] or it["desc"], f"SKIP ({r.get('detail')})")); continue
        if s != 200:
            report.append((it["line"], it["code"] or it["desc"], f"FAILED {s}: {r.get('detail')}")); continue
        report.append((it["line"], r["item_code"], "CREATED")); created.append((it, r))
        if it["qty"] and it["qty"] > 0:
            line = {"item_id": r["item_id"], "quantity": str(it["qty"])}
            if it["serialized"]:
                line["serial_numbers"] = it["serials"]
            lines.append((it, line))
    if lines:
        for i in range(0, len(lines), 50):  # chunks keep each purchase small and retryable
            chunk = lines[i:i + 50]
            s, p = api.call("POST", "/purchases", {"purchase_date": date.today().isoformat(), "reference_no": f"OPENING-STOCK-{date.today().isoformat()}-{i // 50 + 1}",
                                                  "notes": "Opening stock import", "lines": [x[1] for x in chunk], "idempotency_key": uuid.uuid4().hex})
            if s != 200:
                report.append((0, f"opening stock chunk {i // 50 + 1}", f"FAILED {s}: {p.get('detail')}")); continue
            for it, line in chunk:
                s, pend = api.call("GET", "/purchases/pending-costs")  # re-read: every completed line bumps the purchase version
                row = next((x for x in (pend or []) if x["item_id"] == line["item_id"] and x["purchase_id"] == p["purchase_id"]), None)
                if not row:
                    report.append((it["line"], it["code"] or it["desc"], "stock saved but cost row not found - complete cost in Purchases")); continue
                s, r = api.call("POST", "/purchases/complete-cost", {"purchase_id": row["purchase_id"], "purchase_line_id": row["purchase_line_id"],
                                                                      "unit_cost": str(it["cost"]), "version": row["version"], "purchase_version": row["purchase_version"]})
                report.append((it["line"], it["code"] or it["desc"], "opening stock + cost OK" if s == 200 else f"COST FAILED {s}: {r.get('detail')}"))
    for n, r in plan_customers:
        s, c = api.call("POST", "/customers", {"name": r.get("name") or None, "contact_no": r.get("contact_no") or None, "notes": r.get("notes") or None})
        report.append((n, r.get("name") or r.get("contact_no"), "CUSTOMER CREATED" if s == 200 else f"CUSTOMER FAILED {s}: {c.get('detail')}"))

    out = f"import-report-{date.today().isoformat()}.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["line", "item/customer", "result"]); w.writerows(report)
    bad = [x for x in report if "FAILED" in x[2] or "not found" in x[2]]
    print(f"Done. {len(report) - len(bad)} OK, {len(bad)} need attention. Report: {out}")
    for x in bad[:20]:
        print("  !", x)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
