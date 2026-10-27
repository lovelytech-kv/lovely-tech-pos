# Importing the old Excel history (2 years)

`scripts/history_import.py` loads **Inventory_Management_Lovely_Tech.xlsx** and **Repair_Management_Lovely_Tech.xlsx**
with their real dates, in date order (purchases before sales on the same day), through the normal Admin API.
FIFO cost, stock, and every report (monthly sales / profit / repair income / expenses) are rebuilt by the system.

Run it on the shop database **before real daily use starts**, after a backup. It can be run again and again with newer
workbooks (see *Cut-over plan*): every sheet row gets a stable id from its CONTENT (date, item, qty, price; identical rows are
numbered 1, 2, 3), so rows that were already imported are skipped even if rows were inserted or the sheet was re-sorted.

```
pip install openpyxl
python scripts/history_import.py --api http://SERVER:8000/api/v1 --user admin --inventory Inventory_Management_Lovely_Tech.xlsx --repair Repair_Management_Lovely_Tech.xlsx          # dry run
python scripts/history_import.py ... --commit                                                                                                                                    # real import (~15 min)
```

## How each sheet is mapped
| Sheet | Becomes |
|---|---|
| Inventory / Accessories Data | 661 items, same LVT0001.. codes, category, sale price, default warranty |
| Inventory / Purchases | purchases with real dates + unit cost (cost completed, so FIFO profit works) |
| Inventory / Sales | sales with real dates, payment **CASH**, no print, no warranty records |
| Inventory / Phone | one stock item per phone model (old sheet has no IMEI), bought + sold with real dates |
| Inventory / Dmg or Rtn | damage / loss entries at FIFO cost, real dates |
| Inventory / Online Order | customers only (the sales are already in Sales) |
| Inventory / Assets | **not imported** (assets are not stock; keep the sheet) |
| Repair / Part Data, Purchases, Sales | 406 repair-part items (LVT5000+), purchases, sales |
| Repair / Display, PC | one item per kind; each row = unit bought, later sold (LVT7001+, LVT8001+) |
| Repair / Other Repair | 518 repair jobs: income = SALE PRICE, parts cost = COST |
| Repair / Other Exp | expenses (category "Shop expenses (old records)") |

## Verified on your two files (fresh database)
- Sales total **Rs. 7,316,500.00** = the sheets, and all 24 months match exactly; repair income Rs. 576,190; expenses Rs. 18,505.
- Monthly gross profit within ~1% of the sheet (the sheet uses average cost, the POS uses FIFO — small differences are normal).
- Stock balance equals the sheet for all 659 accessory items (2,674 units). 3 items show negative stock because the sheet sold
  them before it recorded their purchase; fix with a stock count.
- Day-End drawer is untouched by history (a new day starts at its opening cash). **Cash In Hands** report, however, now
  includes all history as cash inflows/outflows (you chose "everything CASH"); take that figure as a history total, not the real cash on hand.
- 1 row (Display row 179: sold at Rs. 0) is booked as a loss at cost, exactly as the sheet's own profit (−2,050) does.

## Cut-over plan (the shop keeps working in Excel until the POS goes live)
Until go-live nothing changes in the shop: keep adding rows to the two workbooks as usual.
Rules for the workbooks: do not rename sheets or column headings; add new rows, do not edit old ones. If an old row
must be corrected, tell whoever runs the import (an edited row looks like a new row; `--verify-only` will flag that month).

1. **Rehearsal / pre-load (any time).** Run the full import on the shop database while the POS is not yet in use
   (about 5 minutes, then check the month-by-month verification at the end).
2. **Last Excel day = D-1.** After closing, save both workbooks and take a backup.
3. **Catch-up** with the newest workbooks. Only new rows are added (about 1 minute):
   `python scripts/history_import.py --api ... --inventory ... --repair ... --since <date of the previous import minus 7 days> --until <D-1> --commit`
   `--until` is the cut-over guard: nothing dated after D-1 is ever imported, so it can never clash with POS records.
4. **Verify:** `... --until <D-1> --verify-only` must say ALL MATCH (also printed automatically after `--commit`).
5. **Go live on day D:** Day Start in the POS; stop entering new rows in Excel (keep the files as an archive).
   After this day never run the import again without `--until`.

Options: `--since DATE` (fast, only records on/after that date; overlap is harmless), `--until DATE` (cut-over guard),
`--verify-only` (write nothing, compare months), no `--commit` = dry run.

## Rehearsal on your two files (2026-10-27)
Imported everything up to 31 Aug 2026 (4.5 minutes), then ran the newer data as a catch-up (33 seconds): sales count 5,232,
sales Rs. 7,316,500, repair income Rs. 576,190, expenses Rs. 18,505 — all 24 months match the sheets. Each purchase row is its own
purchase lot, so FIFO profit can differ from the earlier single-run figures by about 0.05% (same-day lots are consumed in sheet order).
