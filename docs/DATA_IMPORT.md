# Importing your real data (items, opening stock, IMEI phones, customers)

Use `scripts/import_data.py`. It talks to the running POS server as **Admin**, so every rule applies
(FIFO purchase lots, IMEI checks, audit log, item codes preserved). Templates: `docs/import_templates/`.

1. Fill `items.csv` (and `customers.csv`) in Excel and save as **CSV UTF-8**.
   - Required per item: `description`, `category`, `item_type`. Everything else is optional.
   - `item_code`: keep your old code (e.g. OLD0042) or leave blank for the next LVT number.
   - Opening stock: `opening_qty` **and** `unit_cost` (needed for correct FIFO profit).
   - Phones with IMEI: item type name ending in "Phone" (or `--serialized-types "Smartphone,Tablet"`), put every IMEI in
     `serials` separated by `;` — the count must equal `opening_qty`.
2. **Dry run first** (writes nothing, lists every problem with its line number):
   `python scripts/import_data.py --api http://SERVER:8000/api/v1 --user admin --items items.csv --customers customers.csv`
3. When it says "Dry run OK", add `--commit`. A report `import-report-<date>.csv` is saved.
4. Safe to re-run the same file: items (by code, or by description when no code) and customers (by phone/name) that
   already exist are skipped. If a line reports "COST FAILED", the stock is saved and the cost can be completed by Admin
   in Purchases → Pending Buy Cost.
5. Take a backup before and after (Admin → Backup).
