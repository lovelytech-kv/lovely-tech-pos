# Lovely Tech POS — Audit & Hardening Batch — 2026-10-02

## Scope
Fresh review of the uploaded integrated V10 source bundle against the locked Requirements v2.0 and Database Technical Blueprint v2.0, followed by a controlled backend/frontend hardening batch.

## Source inspection
- Locked PDFs extracted and reviewed.
- V10 integrated source inventory: 189 files in the V10 archive; 125 Python files, 25 Alembic version files, 26 backend test files, 7 TSX source files, 16 API route files.
- V0 dashboard archive inspected as visual/UX reference only; its Next.js/demo architecture was not imported.
- Static sweep across 176 source/document files found no TODO/FIXME/XXX markers.

## Implemented in this batch
1. **Completed purchase cost correction**
   - Added Admin-only `/purchases/history` contract exposing stable purchase-line IDs plus item/supplier metadata.
   - Added completed purchase history correction controls for cost/date/quantity/reference.
   - Preserved existing controlled correction services, audit trail and FIFO recalculation path.

2. **Supplier assignment**
   - Purchase creation now accepts optional `supplier_id` for Admin-side entry.
   - Server validates active supplier and rejects non-Admin supplier assignment.
   - Added audited Admin supplier correction endpoint.

3. **Item default warranty**
   - Added Admin Item Master API/UI for default warranty.
   - Supported `NONE`, `DAYS`, `MONTHS`, `CHECKING ONLY`, `CUSTOM`.
   - Existing sale-time warranty snapshot remains the source for historical sale warranty records.

4. **Customer warranty history**
   - Customer history now returns warranty claims linked to customer sales, including claim number, decision, outcome, warranty number and invoice reference.
   - Existing cost/profit-hidden customer-facing contract remains unchanged.

5. **Reload one-time rule**
   - Provider restricted to Dialog/Airtel/Mobitel/Hutch.
   - Service rejects a second reload for the same open business day.
   - Alembic migration `0024_reload_once_per_day` adds PostgreSQL trigger protection for concurrent/API paths.
   - Existing historical duplicates are preserved.

## Verification
- Backend `pytest`: **77 passed**.
- Python `compileall`: **passed**.
- `alembic upgrade head --sql`: **passed**.
- Frontend `npm run build`: **UNVERIFIED** — no `node_modules` present in uploaded source environment.
- Playwright: **UNVERIFIED**.
- PostgreSQL 18/LAN/Windows/Tauri: **UNVERIFIED**.
- Thermal/A5 printer and USB barcode scanner: **UNVERIFIED**.
- Google Drive credentials/upload/retry/physical restore: **UNVERIFIED**.

## Remaining material gaps / acceptance items
- Backup emergency-target configuration is still documented/configured at deployment level rather than exposed as a general Admin UI.
- Universal optimistic version protection across every editable transaction is not yet proven.
- Full physical acceptance matrix remains pending.
- Sale-time warranty override and other locked edge paths should continue through the full acceptance matrix rather than being inferred from unit tests.
- Production readiness must remain separate from implementation/automated-test completeness.

## Follow-up hardening — Sale-time warranty override
- 🟢 Locked sale-time warranty override requirement is now implemented server-side and in POS UI.
- 🟢 Supported override types: `NONE`, calendar `DAYS`, calendar `MONTHS`, `CHECKING ONLY`, and controlled `CUSTOM`.
- 🟢 Override fields are included in the sale idempotency request hash.
- 🟢 Historical sale-time warranty stores the exact override used for that sale.
- 🟢 Tests increased from 78 to 81 and all pass.
