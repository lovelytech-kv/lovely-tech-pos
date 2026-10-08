# Lovely Tech POS — Windows LAN Deployment

## Cashier laptop (always-on server)
1. Install PostgreSQL 18 and Python 3.13.
2. Copy the project to a protected folder.
3. Create `backend/.env` from `.env.example`; set a unique `SECRET_KEY`, production `DATABASE_URL`, `APP_ENV=production`, and `BACKUP_ROOT`.
3b. First-time data: run `scripts/bootstrap_security.py` (creates the branch, roles, expense categories and Admin/Cashier users).
5. Run `scripts/windows/Install-LovelyTechServer.ps1` as an Administrator only during installation.
5. Run `scripts/windows/Configure-LovelyTechFirewall.ps1` once on the Private network.
6. Start with `scripts/windows/Start-LovelyTechServer.ps1`.
7. Verify `/health` and `/health/readiness` with `Verify-LovelyTechServer.ps1`.
8. The cashier Windows account remains a Standard User and must not receive PostgreSQL/pgAdmin credentials.

## Owner laptop
Build the client with `scripts/windows/Build-LovelyTechClient.ps1 -ServerUrl http://CASHIER-LAPTOP-IP:8000`. The script validates the URL, uses `npm ci` when a lockfile exists (otherwise `npm install`), runs the frontend production build, then builds the Tauri MSI/NSIS package. The resulting client points to the cashier server API.

Do not commit a real shop LAN IP into `frontend/.env.example`; it intentionally contains the placeholder `CASHIER-LAPTOP-IP`. The actual cashier IP is supplied only at the build step.

## Backup
The POS Backup tab now requests a real encrypted PostgreSQL custom-format dump. Verified files are stored under the configured backup root. `Backup-LovelyTech.ps1` is the host-level scheduled/manual backup path.

## Restore
Restore is intentionally a destructive host operation. The runner requires `--confirm`, creates a verified pre-restore safety backup, restores with `pg_restore --exit-on-error`, and runs a post-restore `SELECT 1`.

## Google Drive
Google Drive is backup/recovery storage, not the live database. After local backup verification, copy/upload the `.ltbak` file to the shop's controlled Google Drive backup location. Do not mount Google Drive as PostgreSQL storage.


## No spare test PC?
See `docs/NO_TEST_PC_STAGING_PLAN.md` (Owner laptop = staging, separate DB/port, then parallel run before go-live).

## Important
- Requires **Python 3.13** (not 3.12 / 3.14).
- Backups are encrypted with `SECRET_KEY`: if it is lost or changed, old backups cannot be restored. Keep a copy offline.
