# Lovely Tech POS — Project Status

## 1. Project Core Rules

- **Architecture:** Offline-first local LAN POS. The Cashier laptop hosts PostgreSQL and FastAPI and must continue operating when the Owner/Admin laptop is offline.
- **Tech stack:** Python 3.13, FastAPI, PostgreSQL 18, SQLAlchemy, Alembic, React, TypeScript, Vite and Tauri 2.
- **Access roles:** Admin and Cashier user roles, separate from SERVER and CLIENT machine roles.
- **Core features:** Sales, inventory with exact FIFO costing, purchases, returns, exchanges, warranty, repairs, cash management, reporting, thermal printing, and encrypted local/Google Drive backups.
- **Deployment:** Same installer should support server and client machines, discover the genuine server without hardcoded IP addresses, and support safe replacement-server recovery.
- **Security:** Enforce permissions on the backend. Cashiers must not access purchase cost, supplier cost, FIFO unit cost, profit, or other restricted financial information.
- **Recovery:** Only VERIFIED backups may be restored. Restore must validate shop identity and fail closed on uncertainty. Avoid split-brain or multiple active writers.

## 2. Current Focus

- Fix zero-IP server discovery and setup-state validation to prevent incorrect server selection and split-brain.
- Continue validating the recent restore interlock and identity-reconciliation changes before accepting them as production-safe.

## 3. Pending Bugs / Features

- Server discovery and setup-state validation, including replacement-server scenarios.
- Thermal bill printer error handling: a printing failure must not roll back a completed sale.
- Google Drive backup synchronization: queue uploads while offline and retry when connectivity returns.
- Backend permission enforcement and tests proving Cashiers cannot access restricted costs/profit data.
- Deterministic negative-stock reconciliation.
- Verify server replacement, recovery-state handling, and single-writer protections.
- Complete desktop packaging and installer validation for Tauri 2.
- Perform isolated PostgreSQL integration testing for backup/restore when explicitly scheduled and safely configured.
- Historical spreadsheet import remains deferred until the final phase and must not start without explicit user instruction.

## 4. Completed / Implemented Work

- Initial architecture and requirements documentation established.
- PostgreSQL 18 and FastAPI base setup; backend health endpoint previously returned HTTP 200.
- Shop identity model and backup-envelope `shop_id` metadata implemented.
- Backup identity validation added to reject missing or malformed shop identity metadata.
- Business-write identity gate and durable restore-state checks implemented.
- Restore reconciliation checks implemented to compare restored shop identity with the selected backup identity.
- Bootstrap/restore interlock implementation added.
- Task 20 implementation report: standalone restore control paths use `settings.backup_root`; a regression test covers an external safety-output directory.
- Task 20 reported verification: 34 tests passed, 1 warning; syntax compilation passed.

## 5. Validation Status / Known Limitations

- Task 20 has not yet been independently accepted; the independent review is pending.
- Cross-process and POSIX locking have not been verified by the reported Windows-focused tests.
- A real PostgreSQL restore has not been proven by the recent mocked-subprocess test runs.
- Do not claim the configured production/shop database was untouched after any test attempt whose database connection behavior was not established.
- Tauri production installer/EXE generation and full installation/recovery validation remain outstanding.
- Overall feature completeness and production readiness have not been established.

## 6. Working Rules

- Do not use Git in this workflow.
- Keep coding tasks small and scoped; verify changes before moving to the next task.
- Avoid running tests that may connect to the configured shop database unless their database dependencies are explicitly isolated.
- Do not install packages or change system settings without explicit approval.
- Do not start historical data import until explicitly instructed.
- Record test commands and actual results; distinguish implemented, tested, independently reviewed, and production-verified work.

## 7. Overall Progress

- **Estimated overall completion:** approximately 46% (rough planning estimate, not a test-derived metric).
- **Next action:** independently review Task 20, fix any confirmed safety defects, then continue with zero-IP discovery and setup-state validation.