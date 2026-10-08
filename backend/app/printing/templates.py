from __future__ import annotations
from decimal import Decimal
from typing import Iterable


def _money(v: Decimal | int | str) -> str:
    return f"Rs. {Decimal(str(v)).quantize(Decimal('0.01')):,.2f}"


def render_receipt_text(*, shop_name: str, invoice_no: str, lines: Iterable[dict], subtotal: Decimal, discount_total: Decimal, grand_total: Decimal, payments: Iterable[dict], footer: str = "Thank you") -> str:
    out = [shop_name.strip(), f"Invoice: {invoice_no}", "-" * 32]
    for line in lines:
        name = str(line.get("description", ""))[:22]
        qty = line.get("quantity", 1)
        total = line.get("final_total", 0)
        out.append(f"{name:<22} {qty:>5} {_money(total):>14}")
    out += ["-" * 32, f"Subtotal:       {_money(subtotal)}", f"Discount:       {_money(discount_total)}", f"TOTAL:          {_money(grand_total)}"]
    for p in payments:
        out.append(f"{str(p.get('method','')):<16}{_money(p.get('amount',0)):>16}")
    out += ["-" * 32, footer.strip()]
    return "\n".join(out) + "\n"


def render_a5_warranty_text(*, shop_name: str, claim_no: str, invoice_no: str | None, item_description: str, serial_number: str | None, purchase_date: str, warranty_expiry: str, customer_name: str | None = None, notes: str | None = None) -> str:
    rows = [shop_name.strip(), "WARRANTY DOCUMENT", "", f"Claim: {claim_no}"]
    if invoice_no: rows.append(f"Invoice: {invoice_no}")
    rows += [f"Item: {item_description}", f"Serial/IMEI: {serial_number or '-'}", f"Purchase Date: {purchase_date}", f"Warranty Expiry: {warranty_expiry}"]
    if customer_name: rows.append(f"Customer: {customer_name}")
    if notes: rows += ["", f"Notes: {notes}"]
    rows += ["", "Keep this document for warranty claims."]
    return "\n".join(rows) + "\n"
