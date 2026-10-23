# Lovely Tech POS — Development Status
- Windows server startup hardening: **IMPLEMENTED** — PostgreSQL readiness retry, Windows startup task installer, and production preflight script.

Current stage: **Requirement completion / pre-deployment hardening**

## Latest verification
- Backend pytest: **51 passed**
- Python compileall: **passed**
- FastAPI app/routes import: **117 routes loaded**
- Alembic head: **0020_warranty_rule_snapshot**
- Frontend production build: **UNVERIFIED** (runtime dependencies unavailable in isolated environment)
- Playwright acceptance: **UNVERIFIED** (frontend runtime dependencies unavailable)
- Windows/LAN/PostgreSQL/printer/scanner/Google Drive physical tests: **UNVERIFIED**

## Latest completion batch
- Report export now uses `VITE_API_BASE` for LAN/Tauri clients.
- Added stock report export support (PDF/XLSX).
- Added Other Income UI alongside Expense entry.
- Added POS cash-in entry in Day/Cash UI.
- Settlement proof reprint event is recorded after successful credit settlement.

Deployment remains intentionally **not started** until frontend/runtime acceptance is verified.

## Additional completion batch — 2026-09-26
- Added authenticated `/backup/status` endpoint so both Admin and Cashier can see backup status/last verified backup time without exposing restore points.
- Dashboard and Cash/Day UI now display the latest verified backup status/time.
- Added a dedicated Admin Profit export type (PDF/XLSX) using the locked profit-domain breakdown.
- Backend verification after this batch: 51 passed; Python compile check passed.
- Frontend runtime build/Playwright remain environment-unverified because npm dependency installation timed out in the isolated environment.


### V42 completion batch — 2026-09-26
Frontend acceptance hardening added serialized sale selection, customer creation, richer repair finalization, warranty lookup/claim notes, target progress history, and a complete Documents/Reprint tab. A settlement reprint endpoint mismatch was corrected. Backend remains 65/65 passing. Frontend production build remains UNVERIFIED because React/Vite dependencies could not be installed in the isolated environment.

### V43 hardening batch — 2026-09-26
- Shift End and Day End now enforce a verified backup before close when `REQUIRE_VERIFIED_BACKUP_FOR_CLOSE` is enabled (default: enabled). A verified local backup is sufficient; configured alternate storage/Google Drive sync remains available for recovery workflow.
- Product warranty records now snapshot `duration_value` and `custom_rule` from the active item warranty default so sale-time CUSTOM rules remain historically reproducible.
- Customer History in POS is now an inline history view showing sales, settlements and repairs instead of only a count alert.
- Added migration `0020_warranty_rule_snapshot`.
- Hardened migration `0019_manual_warranty_reference_unique` so its duplicate-data safety check is skipped only during offline SQL generation; online migration still checks existing duplicates and fails clearly.
- `alembic heads`: `0020_warranty_rule_snapshot`.
- Alembic offline SQL generation: PASS through migration `0020`.
- Backend pytest: 51 passed; Python compileall: passed.
- Frontend production build/Playwright and physical Windows/LAN/printer/Google Drive acceptance remain UNVERIFIED because the isolated environment does not have installed frontend runtime dependencies or shop hardware/services.


### V44 completion batch — 2026-09-26
- Added persistent `TargetProgressSnapshot` records so completed target periods retain immutable historical achieved value/percentage instead of relying only on live recalculation.
- Day End now captures completed target periods atomically with the close transaction. Duplicate snapshots for the same target version are prevented by a database unique constraint.
- Added Admin-only `/reports/target-history` endpoint and connected the Admin target-history UI to persisted snapshots.
- Added migration `0021_target_progress_snapshots`.
- Alembic head: `0021_target_progress_snapshots`.
- Alembic offline SQL generation through head: PASS.
- Backend pytest: **53 passed**; Python compileall: passed; FastAPI routes loaded: 119.
- Frontend production build/Playwright and physical Windows/LAN/PostgreSQL/printer/scanner/Google Drive acceptance remain UNVERIFIED because the isolated environment cannot complete npm dependency installation and does not have the shop hardware/services.


## V44/V45 hardening follow-up — 2026-09-26
- Target historical progress is persisted as immutable snapshots at Day End; duplicate target-version snapshots are blocked by a unique constraint.
- Repair payments, return refund payments and credit settlements now accept unique idempotency keys and safely return the original event on an identical retry instead of creating duplicate financial movements.
- Warranty supplier outcomes/replacements now reject duplicate execution after an outcome has already been recorded.
- Frontend payment/refund/settlement actions now keep a stable idempotency key until the operation succeeds.
- Verification: 56 backend tests passed, Python compile passed, 119 FastAPI routes loaded, and Alembic offline SQL generation reached `0022_payment_idempotency` successfully.
- Frontend production dependency installation still timed out in the isolated environment, so browser build/Playwright remain explicitly UNVERIFIED.

## V47 Hardening Batch
- Test contract path robustness fixed: repository contract tests now resolve source files from the repository root, so `pytest -q` passes from both the project root and `backend/` working directories.
- Backend verification: 58/58 tests passing from both supported working directories.
- Python compileall: PASS.
- Alembic head: 0023_history_immutability.
- Full offline Alembic SQL generation through head: PASS.
- Frontend npm dependency installation remains UNVERIFIED in the isolated environment because the install timed out; no browser-build PASS is claimed.


## V48 Production Hardening Batch
- Windows server startup hardening implemented: PostgreSQL readiness retry before migrations/server start.
- Windows startup-task installer added for automatic POS server recovery after cashier-laptop reboot.
- Windows production preflight added for Python 3.13, virtualenv, `.env`, PostgreSQL reachability, API port and SECRET_KEY prerequisites.
- Deployment contract tests added.
- Backend verification: **65/65 tests passing** from both supported working directories.
- Python compile: **PASS**. Alembic head: `0023_history_immutability`; offline migration SQL generation: **PASS**.
- Frontend production build and Playwright remain **UNVERIFIED** because the isolated environment cannot complete npm dependency installation.

## V49 Frontend Build/Deployment Hardening
- Frontend build contract hardened: `Build-LovelyTechClient.ps1` now validates the server URL, uses `npm ci` when a lockfile is present, otherwise `npm install`, then runs the production build and Tauri package build.
- `frontend/.env.example` no longer contains a shop-specific LAN IP; the cashier server address is supplied at client build time.
- Added frontend/deployment contract tests to the backend suite.
- Backend verification: **65/65 tests passing** from both supported working directories; Python compile and Alembic offline generation remain PASS.
- Frontend production build and Playwright remain explicitly **UNVERIFIED** because dependency installation is unavailable/times out in the isolated environment.

## V50 — Production Acceptance Runner Hardening
- Added `scripts/windows/Production-Acceptance.ps1` to execute the real server health/readiness check and, when requested, backend tests and frontend production build on a Windows deployment machine.
- The acceptance runner keeps backend-test and frontend-build failures explicit; no environment-dependent result is treated as PASS without execution.
- Added a Windows deployment contract test for the acceptance runner.
- Source-level backend verification after V50 changes: pending final verification in this snapshot.


## 2026-10-02 — Production hardening batch
- Added Admin purchase-history contract with stable purchase-line IDs and completed-cost correction UI.
- Added Admin supplier assignment during purchase entry and audited supplier correction.
- Added Item Master default warranty management with historical sale-time snapshot compatibility.
- Added warranty claims to customer history where claims are linked to a customer sale.
- Enforced one reload per business day server-side, including provider validation and PostgreSQL concurrency trigger.
- Added focused contract tests. Backend suite: 77 passed.
- Alembic offline migration SQL: passed; new head is `0024_reload_once_per_day`.
- Frontend build/Playwright, Windows/Tauri, LAN/PostgreSQL, printer/scanner and real Google Drive tests remain UNVERIFIED.

## Batch 2026-10-02 — Sale warranty override hardening
- 🟢 Sale lines now accept explicit sale-time warranty overrides for `NONE`, `DAYS`, `MONTHS`, `CHECKING ONLY`, and controlled `CUSTOM` rules.
- 🟢 Server-side validation rejects invalid override combinations before transaction processing.
- 🟢 Historical `ProductWarranty` records snapshot the override used at sale time; later Item Master default changes do not affect the record.
- 🟢 Sale idempotency request hashing now includes warranty override fields so a retry cannot silently change the warranty definition under the same key.
- 🟢 POS cart exposes a per-line warranty override control while retaining Item Master default as the normal option.
- 🟢 Inventory item search exposes only non-sensitive warranty-default metadata needed by the cashier POS; no cost/profit data is added.
- 🟢 Backend tests: 81 passed; Python compile check passed.
- 🟡 Frontend Vite build and Playwright remain UNVERIFIED because `node_modules` is not present in the supplied source environment.

## Batch 2026-10-02 — Concurrency & Failure Safety
- Added stale-version conflict protection to repair, purchase, warranty, day-session, approval, and selected Admin-user mutations.
- Successful controlled mutations now advance record versions.
- POS request payloads updated to carry the required versions.
- Backend regression suite: **84 passed**.
- Python compile check: **PASS**.
- Frontend Vite build / Playwright: **UNVERIFIED** because dependencies are not installed in the supplied source bundle.
- PostgreSQL/LAN/Windows/Tauri/printer/scanner/physical restore acceptance remains deployment-level work.

## Frontend V0-Inspired UI Batch — 2026-10-02
- Backend source frozen at V13 for this batch; no backend source changes made.
- Reused the supplied V0 dashboard as a visual/interaction reference only; V0 demo architecture/data were not imported.
- Reworked the real frontend shell: sidebar navigation, workspace header, LAN/branch status, user controls, search affordance, spacing, cards, forms, tables, buttons, responsive layout, and login screen.
- Preserved the existing real POS API calls and business workflows.
- Frontend dependency installation/build could not be completed in this environment because `npm install` timed out; source-level TS/TSX parser validation passed for all frontend source files.


## V18 Frontend Purchase/Supplier Hardening — 2026-10-02
- Reworked the active Purchases workspace without backend changes.
- Added Admin supplier selection during purchase entry.
- Added version-aware pending-cost completion.
- Added purchase history using the dedicated history endpoint with date filtering.
- Added audited Admin correction UI for cost, quantity, date, reference, and supplier assignment, including re-authentication and optimistic-lock versions.
- Preserved cashier cost privacy and idempotent purchase submission.

## Verification & bug-fix batch — 2026-10-20 (first run on real PostgreSQL + real browser)
Verified by actually executing (previously "UNVERIFIED"):
- Backend pytest against PostgreSQL 16: **263 passed**. Fresh `alembic upgrade head` + `bootstrap_security.py` + live uvicorn + `scripts/smoke_api.py`: **ALL PASS**.
- Frontend: `tsc -b` PASS, `vite build` PASS, `vitest` 87/87 PASS. Real Chromium (Playwright) drove login, every tab as Cashier and Admin, Day Start and Repair intake + advance payment against the live server.

Defects found and fixed (each has a regression test):
- **Frontend called `/operations/...` endpoints that the server never served** (Day Start/Shift/Day End, Reload, Cash-in, Reopen, all Repair screens, approval review, credit settlements → HTTP 404). Guarded by `test_frontend_api_paths.py`.
- **Adding a repair part crashed (HTTP 500)**: `repair_parts.stock_movement_id` referenced a random UUID instead of the FIFO movement.
- **Shift End did not require a verified backup** (only Day End did) — now enforced (Requirements 15).
- **mDNS advertisement ran its blocking sync API on the event-loop thread**: LAN discovery never registered and startup stalled ~25 s. Now runs in a worker thread (startup ~3 s).
- `/api/v1/health` (probed by the client's online indicator) did not exist; alias added.
- Vite dev server had no `/api` proxy although `.env.example` assumed one.
- Earlier in this batch: item codes now `LVT0001` style, `ITEM_EDIT` granted to Cashier by bootstrap, `POST /returns` and exchange crashes, repair-payment kwargs, IPv6 discovery URLs, missing `openpyxl`/`reportlab` dependencies.

Still NOT verified (needs the real shop machines): Windows/Tauri packaging, two-client LAN concurrency, thermal/A5 printers, USB scanner, real Google Drive upload.

Resolved (2026-10-21): the open design question above is closed by the automatic close backup below.

## Automatic backup at Shift End / Day End — 2026-10-21
- No backup button: pressing Shift End or Day End makes the server take a backup automatically (`pg_dump` → encrypt → decrypt-verify → Google Drive upload when configured). The close is performed **only after a backup is VERIFIED**; until then the endpoint answers `202 {backup_status: RUNNING, attempt, max_attempts}` and the client (Cash / Day screen) shows progress and asks again every 3 s.
- **Automatic retries**: a failed attempt is retried with exponential back-off (2 s, 4 s, … capped at `BACKUP_CLOSE_RETRY_MAX_DELAY_SECONDS`) up to `BACKUP_CLOSE_MAX_ATTEMPTS` (default 10). If every attempt fails the close is refused with `503 BACKUP_FAILED`, **nothing is changed**, the failure is audited (`BACKUP_AUTO_CLOSE_FAILED`), and the next press starts a fresh retry cycle. Failed attempts are stored as `FAILED` points and are never restorable.
- Google Drive upload is retried (`BACKUP_UPLOAD_ATTEMPTS`). If Drive stays unreachable the backup falls back to the separate `BACKUP_ALTERNATE_TARGET` (USB/external/network folder) where the copy is verified too; the point stays `PENDING_SYNC` and a background task (`BACKUP_SYNC_RETRY_INTERVAL_SECONDS`) uploads queued backups once the network returns. With no alternate target configured the verified local backup is accepted (as before).
- A verified backup younger than `BACKUP_CLOSE_REUSE_SECONDS` (default 60 s, minimum 30 s) satisfies a close, so fixing a validation error and pressing Day End again does not dump the database twice.
- The cashier only sees progress/“failed” text; the technical reason (with DB password and secret redacted) is Admin-only (audit log / backup points).
- Verified live: real `pg_dump` via the UI (202 → backup → 200 SHIFT_ENDED); a `pg_dump` that failed twice then worked completed Shift End automatically on attempt 3; with `pg_dump` missing the close was refused (503) and the day stayed OPEN.

## Serialized (IMEI) phones — verified 2026-10-23

Found during the UI sweep: nothing could ever create a `SerializedUnit`, so phones with an IMEI could not be
purchased into stock or sold with an identity.

- Purchase: each serialized line needs exactly one IMEI per whole unit (trimmed + upper-cased); duplicates inside the
  entry or already in the system are rejected, atomically. IMEI-tracked purchase quantity cannot be corrected afterwards.
- Sale: a serialized item cannot be sold without an in-stock `serialized_unit_id`; the same phone cannot be sold twice.
  Good returns put the phone back to IN_STOCK. Warranty lookup by IMEI works.
- UI: Purchases has an IMEI box per phone line; POS gives every phone its own cart line, requires its IMEI before
  checkout and lists only IN_STOCK units. Fixed the money helper `moneyTimesQty` (divisor was 100x too large).
- Tests: `backend/tests/test_e2e_serialized.py`, `frontend/src/services/money.test.ts`, plus a real-Chromium run
  (buy 2 IMEIs as cashier, sell both through the POS, units end SOLD, no API errors).
- Run the backend suite on a FRESH database each time (day sessions persist between runs) and with the default
  `REQUIRE_VERIFIED_BACKUP_FOR_CLOSE=true`: 283 passed.

Still open: purchase payment method is asked/stored although Requirements 08 says it must not be; stock adjustment /
damage on serialized items can desync units from movement-based stock; `SerializedUnit.purchase_lot_id` is not linked.
