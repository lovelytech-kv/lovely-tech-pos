# Importing the old Excel history (2 years)

`scripts/history_import.py` loads **Inventory_Management_Lovely_Tech.xlsx** and **Repair_Management_Lovely_Tech.xlsx**
with their real dates, in date order (purchases before sales on the same day), through the normal Admin API.
FIFO cost, stock, and every report (monthly sales / profit / repair income / expenses) are rebuilt by the system.

Run it ONCE, on the shop database **before real daily use starts**, after a backup. Safe to re-run after an interruption
(every record has a fixed idempotency key / reference `HIST-...`; already imported rows are skipped).

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
