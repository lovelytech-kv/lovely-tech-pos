# Lovely Tech POS — Concurrency & Failure Safety Batch
Date: 2026-10-02

## Scope
This batch hardens stale-edit protection and state-transition safety for mutable operational records.

### Implemented
- Repair status/finalize/deliver/cancel mutations now require the current repair `version` from the POS client.
- Repair detail exposes the current `version`; successful controlled mutations advance it.
- Purchase cost completion and purchase cost/date/quantity/reference corrections require current purchase-line/purchase versions and advance versions after success.
- Purchase supplier assignment requires the current purchase version.
- Warranty claim supplier/damage/outcome/replacement decisions require the current claim version and advance it after success.
- Day opening correction and Day End require the current day-session version and advance it after success.
- Approval review checks the approval-request version and advances it after review.
- Admin user discount-limit and role changes require the current user version and advance it after success.
- POS payloads were aligned for repair, warranty, purchase, and Day End flows.
- Existing row-level `SELECT ... FOR UPDATE` protections remain in place for the affected transactional paths.
- Existing audit/history immutability migrations remain unchanged and covered by regression tests.

## Conflict behavior
If a stale screen submits a mutation, the API returns HTTP 409 with a reload-oriented message instead of overwriting the newer record.

## Automated verification
- Backend test suite: **84 passed**.
- Python compile check: **PASS**.
- ZIP integrity: checked after packaging.
- Frontend Vite build: **NOT VERIFIED** in the supplied source environment because `frontend/node_modules` is not present.
- Playwright/browser acceptance: **NOT VERIFIED**.
- PostgreSQL/LAN/Windows/Tauri/printer/scanner/physical backup-restore acceptance: **NOT VERIFIED**.

## Remaining hardening / acceptance items
This batch does not claim that every mutation endpoint in the application has a version contract. Low-risk/admin-only and append-only operations still need a separate endpoint-by-endpoint acceptance audit. Physical deployment and real-shop concurrency testing remain required before production sign-off.
