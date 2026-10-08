# Lovely Tech POS — Production Acceptance Matrix

This checklist is the final environment-verification gate. Automated tests do not substitute for these shop-environment checks.

| Area | Acceptance test | Expected result |
|---|---|---|
| LAN | Owner laptop connects while cashier laptop hosts server | POS works over LAN; PostgreSQL is never exposed directly |
| LAN | Cashier laptop reboots | PostgreSQL/FastAPI restart and POS reconnects after startup |
| Windows boot | Startup task installed | POS server starts automatically after Windows boot and waits for PostgreSQL readiness |
| Windows preflight | Run `Preflight-LovelyTechServer.ps1` | Python/.venv/.env/PostgreSQL/secret prerequisites are reported before production start |
| Offline | Internet disconnected | Core LAN sale/repair/stock workflows continue |
| Auth | Cashier requests admin-only endpoint | HTTP 403; no hidden cost/profit data returned |
| Lock | Admin idle >5 min | Session requires login again |
| Lock | Cashier idle >60 min | Session requires login again |
| Sale | Double-click Complete Sale | One committed sale/invoice only |
| Sale | Printer disconnected after commit | Sale remains completed; reprint remains available |
| FIFO | Negative stock sale followed by purchase | Deterministic reconciliation; original purchase lot retained |
| Return | Good return | Stock/FIFO lineage restored correctly |
| Return | Damaged return | Damage/Loss cost recorded correctly |
| Repair | Part usage then part removal | Good part restores lineage; damaged part remains loss-review path |
| Repair | Delivery with outstanding balance | Blocked unless required Admin approval is supplied |
| Warranty | Expired claim | Exact expired status; claim cannot proceed as active warranty |
| Serial | Duplicate active IMEI/serial | Sale/registration blocked |
| Day | Shift End then Continue Today | Business day remains open when Admin continues |
| Day | Day End denomination mismatch | Difference + mandatory reason recorded |
| Backup | Backup interrupted | Previous VERIFIED point remains valid |
| Restore | Restore verified point | Safety backup → restore → integrity check → audit |
| Restore | Unverified backup selected | Restore blocked |
| Printing | ESC/POS printer online | Receipt printed through TCP 9100 |
| Printing | Windows A5 printer online | RAW spooler print succeeds |
| Printing | Printer unavailable | Transaction is not rolled back |
| Security | Permission removed from Cashier | API immediately rejects action |
| Recovery | Cashier password reset | Admin verification required; forced password change next login |

## V49 Frontend Build/Deployment Hardening
- Frontend build contract hardened: `Build-LovelyTechClient.ps1` now validates the server URL, uses `npm ci` when a lockfile is present, otherwise `npm install`, then runs the production build and Tauri package build.
- `frontend/.env.example` no longer contains a shop-specific LAN IP; the cashier server address is supplied at client build time.
- Added frontend/deployment contract tests to the backend suite.
- Backend verification: **65/65 tests passing** from both supported working directories; Python compile and Alembic offline generation remain PASS.
- Frontend production build and Playwright remain explicitly **UNVERIFIED** because dependency installation is unavailable/times out in the isolated environment.
