# Lovely Tech POS — Frontend Requirements Audit V10

## Source of truth
- `Lovely_Tech_POS_Final_Requirements_v2.0.pdf`
- `Lovely_Tech_POS_Database_Technical_Blueprint_v2.0.pdf`
- Current Claude V8 source baseline

## Frontend items verified / implemented
- Separate Dashboard, POS/Sales, Items, Repairs, Warranty, Stock, Purchases, Day/Cash, Reports, Returns, Expenses, Documents, Admin and Backup navigation.
- Pure red/black glass-morphism theme with lightweight entrance/metric/hover animations.
- Item Master create/edit flow with category, item type, brand/model, optional master sale price, barcode and variants/compatibility.
- Item code remains backend allocated; frontend does not fabricate human numbers.
- Sales cart supports custom price, discount, split cash/card/online payments, cash received/change, manual invoice reference, admin credit sale, customer creation/history and serialized-unit lookup.
- Sale retry uses stable idempotency key; processing state blocks double submission.
- Returns, refund payments and exchange linking are exposed.
- Repair intake is now single-source: the dedicated RepairForm is the only new-job form; management screen handles existing jobs, parts, payments, status and finalization.
- Repair advance retry preserves original amount/method and stable idempotency key.
- Repair parts, warranty lookup/claims, stock adjustment and warranty item selection use searchable item selectors instead of requiring raw UUID entry.
- Stock screen exposes stock count, negative-stock warning, serial/IMEI lookup and batch-age view.
- Purchases support cashier entry without cost, admin pending cost completion, history and pending-line reference/date/quantity correction.
- Day Start, physical denomination count, expected/actual cash, live difference, Shift End, Continue Today, Day End, reload, other cash-in and Admin reopen are exposed.
- Admin opening-cash correction UI now exists with denomination validation and re-authentication.
- Expense/Other Income entry and Admin approval are exposed; custom expense-category management is exposed.
- Supplier master management is exposed to Admin.
- Reports now load the selected operational report on screen instead of only changing the export type; Daily/Monthly/Yearly/custom date controls and PDF/Excel export are present.
- Dashboard includes quick actions, day/backup status, target progress and lightweight animations.
- Documents/reprint search is exposed.
- Admin users, discount limits, password reset, permissions, targets, approvals, stock adjustment and audit are exposed.
- Backup create/verify/sync/restore workflow is exposed with Admin-only restore.

## Remaining gaps that cannot be truthfully fixed by frontend-only work
1. **Completed purchase cost correction UI** — backend has `/purchases/correct-cost`, but the purchase-history response does not expose purchase-line IDs needed to invoke it safely for completed lines. A backend read endpoint/response extension is required.
2. **Item default warranty management** — the locked requirement says the Item Master has a default warranty copied into sale-time warranty. The current backend has `WarrantyDefault` storage/use in sales, but no admin API route to create/edit those defaults. This is a backend capability gap, not a frontend-only gap.
3. **Customer history warranty claims** — the current customer-history API returns sales, settlements and repairs but not warranty claims, while the requirements describe customer history as covering warranty claims. Backend response support is required.
4. **Supplier assignment on purchase** — the database/model has supplier linkage, but the current `PurchaseCreateIn` forbids `supplier_id` and the purchase service does not accept it. Admin supplier master exists, but attaching a supplier to a purchase requires backend contract work.
5. **Reload one-time rule** — the requirements say Reload is entered once at Day End. The current backend accepts multiple reload rows for an open day. Frontend-only local state cannot enforce this reliably after restart; backend enforcement is required.
6. **Backup emergency-target configuration UI** — the requirements describe a separate local/USB/external/network fallback target. Current deployment/configuration scripts provide the operational foundation, but there is no general in-app target configuration screen. This can remain deployment configuration if deliberately locked that way.

## Environment verification still pending
- Actual `npm run build` with installed dependencies.
- Playwright browser acceptance.
- Actual Windows/Tauri runtime after this frontend batch.
- Physical printer/scanner tests.
- Real LAN/production PostgreSQL acceptance.
- Google Drive credential/interruption tests.

## Decision
The V10 frontend is suitable to move to **Windows build/staging acceptance**, but the six backend/contract gaps above must not be hidden as if frontend work completed them. They should be handled as a separate controlled backend-hardening decision before final production sign-off.
