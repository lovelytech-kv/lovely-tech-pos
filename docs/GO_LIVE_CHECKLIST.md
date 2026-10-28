# Lovely Tech POS – Go-live checklist

State: backend suite 308 passed (real PostgreSQL), frontend 92 passed, live smoke ALL PASS, browser sweeps of POS, Purchases, Repairs, Warranty, Returns, Documents, Admin (Targets, users, password reset) done.

## A. Shop pilot (needs the shop PC – see NO_TEST_PC_STAGING_PLAN.md)
1. Install on a staging copy (not the real DB): Windows scripts in `scripts/windows`, `alembic upgrade head`, `bootstrap_security.py`.
2. Open the Tauri app on both laptops over the LAN; check server discovery.
3. Print a bill, a repair slip and a settlement proof; scan an item barcode and an IMEI; check the cash drawer/printer.
4. Run Day Start -> a few sales/repairs/expenses -> Shift End -> Day End; confirm the automatic backup is verified and (if configured) uploaded to Google Drive.
5. Restore that backup onto a spare database (`POST /backup/restore/{id}?confirm=true`).

## B. Cut-over day (see HISTORY_IMPORT.md)
1. Finish the last day in Excel. Stop using Excel.
2. `history_import.py` catch-up with `--until <last Excel day>`, then `--verify-only` must say ALL MATCH.
3. Count the real stock; fix differences with Stock Adjustment (Admin; IMEI phones are ticked by IMEI).
4. Change the default Admin/Cashier passwords; Day Start in the POS.

## C. Known, accepted limits
- Imported history is booked as CASH (owner's decision); Cash In Hands report therefore includes all history.
- FIFO per-row purchase lots can shift profit by ~0.05% between full re-imports.
- The sheet's Assets tab is not imported; 3 items show negative stock because of the order of entries in the sheet (fix with a stock adjustment after counting).
- Serialized units are not linked to a purchase lot (cost is per item lot, not per IMEI) – not required by the requirements.
