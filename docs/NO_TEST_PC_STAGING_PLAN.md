# Staging plan — only 2 laptops (Owner + Cashier), no spare test PC

Rule: **real shop data and the cashier's live work never touch an untested build.**
The Owner laptop is the test machine until the acceptance list below passes.

## Prerequisites (both laptops)
- **Python 3.13 exactly** (the project requires >=3.13,<3.14; 3.12/3.14 will not install).
- PostgreSQL 18; add `C:\Program Files\PostgreSQL\18\bin` to PATH (needed for pg_dump/pg_restore/psql backups).
- Node 20+ and Rust (Tauri) only on the Owner laptop (client build).

## Phase A — Owner laptop as staging server (fake data only)
1. `powershell -ExecutionPolicy Bypass -File scripts\windows\Install-LovelyTechServer.ps1` (creates venv + installs backend + test tools).
2. `scripts\windows\Setup-Staging.ps1 -StagingDbPassword "<strong password>"` — creates separate DB `lovely_tech_pos_staging` + `backend\.env.staging` (port 8001).
3. Bootstrap (from `backend`, with `LTPOS_ENV_FILE=.env.staging`):
   `ADMIN_USERNAME=admin ADMIN_PASSWORD=... CASHIER_USERNAME=cashier CASHIER_PASSWORD=... python ..\scripts\bootstrap_security.py` (branch + roles + expense categories are created automatically; set `BRANCH_CODE`/`BRANCH_NAME` if wanted).
4. `scripts\windows\Start-LovelyTechServer.ps1 -Port 8001 -EnvFile .env.staging`
5. `python scripts\smoke_api.py http://127.0.0.1:8001 admin <pw> cashier <pw>` — all lines must PASS.
6. From `backend`: `python -m pytest -q` — send me every failure.
7. Build client: `Build-LovelyTechClient.ps1 -ServerUrl http://127.0.0.1:8001`, then walk the manual checklist.

## Phase B — manual acceptance (fake data, Owner laptop)
Sale (cash/card/split) · double-click save · discount over cashier limit → approval · negative stock then purchase · return + exchange (old 1000, charge 200, new 1500 → refund 800, pay 1500) · repair full cycle with parts + advance + partial final · warranty claim · credit sale + settlement · Day Start/End/Shift End · **backup → wipe staging DB → restore → check data** · kill the server mid-sale (power-loss test) · cashier cannot see cost/profit in UI or API.

## Phase C — two-laptop LAN test (after-hours, still staging DB)
Install server on the Cashier laptop with a **separate staging DB + port 8001**. Owner laptop client points to it. Test firewall (Private network profile!), concurrent sales from both, printer, barcode scanner, restart-and-auto-start.

## Phase D — parallel run, then go-live
1. Create the **production** DB/.env (new strong SECRET_KEY — store it safely; **backups cannot be decrypted without it**), run `Protect-LovelyTechServer.ps1`.
2. For 1–2 weeks keep the old method as the source of truth; enter the same sales in the POS.
3. Take a verified backup + restore drill on production before the old method is dropped.
4. Never reuse staging data/secret in production.
