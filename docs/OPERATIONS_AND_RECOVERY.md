# Lovely Tech POS — Operations and Recovery

This document describes the intended Windows/LAN workflow. It is not evidence that a production installation, LAN, or restore has passed acceptance. Do not use real shop data for staging.

## Roles and deployment

- **Server:** Cashier laptop, normally powered on during business hours. Runs PostgreSQL and FastAPI. Cashier's Windows account should be Standard User; database and Windows Administrator credentials remain protected.
- **Client:** Owner/Admin and other POS clients communicate with the server API on the private LAN. Clients do not connect directly to PostgreSQL.
- Machine role (`SERVER` / `CLIENT`) is independent of authenticated user role (`ADMIN` / `CASHIER`).
- The target is one role-aware installer/executable. The current server scripts and client packaging script are separate; do not represent the single-installer requirement as implemented.
- **Development/staging:** Use the Owner laptop and an explicitly separate staging database/port with synthetic data until acceptance passes. Never reuse staging database contents or secrets in production.
- **Internet:** Core LAN POS operation must work without Internet. Google Drive is optional backup transport, not live synchronization.

The Owner/Admin client may be switched off without stopping the Cashier server. This is an intended topology requirement; shop acceptance must still verify it with the actual server and other clients.

## Prerequisites to verify

- Backend project metadata requires Python `>=3.13,<3.14`.
- PostgreSQL 18 is the agreed target. Verify the installed server, service startup, `pg_dump`, `pg_restore`, and `psql` versions on the actual host.
- Windows server scripts include install, preflight, startup, task setup, firewall setup, and health/readiness verification under `scripts/windows/`.
- Windows desktop packaging additionally requires Rust stable/Cargo, Tauri CLI, Microsoft C++ Build Tools, and WebView2. The prerequisite audit found WebView2 152.0.4191.66; Rust/Cargo were not found in standard locations, and C++ Build Tools were not found in checked standard locations. Verify these before attempting packaging.
- Keep production `.env` and all secrets out of source control and documentation. Use a unique production `SECRET_KEY` and database credentials; do not reuse staging secrets.

## Server setup sequence

1. Verify the host is the intended always-on Cashier server and that PostgreSQL is installed and starts with Windows.
2. Install the backend using `scripts/windows/Install-LovelyTechServer.ps1`; use elevated permissions only for installation steps that require them.
3. Create a protected production environment file from the example. Configure the production database URL, unique `SECRET_KEY`, branch, API port, and backup root. Set the backup root to storage separate from the PostgreSQL data/working directory.
4. Run database migrations with Alembic only after reviewing the target database and taking an appropriate backup. Never point a staging or acceptance command at production accidentally.
5. Bootstrap the initial branch, roles, permissions, and Admin/Cashier accounts using the supported bootstrap flow. Do not put passwords or tokens in logs or docs.
6. Run server preflight and startup scripts. Verify `/health` and `/health/readiness`; verify database readiness before allowing POS use.
7. Configure the Windows Firewall only for the private LAN profile and required API port. PostgreSQL remains server-local and is not exposed to clients.
8. Configure desktop clients through runtime discovery. A manual address is an identity-checked fallback. Do not bake a fixed LAN address into production bundles.
9. Verify the Cashier workstation remains a Standard User and does not receive database/admin credentials.

The current client build wrapper requires a `-ServerUrl` reachability-check argument and invokes `cargo tauri build`; this is a packaging-script interface, not the target end-user installer workflow. It must not be embedded as the production API address. No Tauri artifact had been generated in the recorded prerequisite audit. The target installer should not require ordinary operators to enter an IP or configure development/runtime dependencies.

## Client setup and server discovery

- Fresh-machine probing for a local server must be limited to `127.0.0.1`.
- Persist the selected server/client role and preserve it on later launches.
- A CLIENT must confirm server identity and valid setup state before READY.
- On bootstrap success, persist the authenticated session through the shared client mechanism, refresh discovery, compare the refreshed identity with the verified identity, and require `setup_state === READY`.
- Discovery failure, identity mismatch, or non-READY setup state must remain a recoverable setup error. Retrying discovery must not repeat the shop bootstrap request.
- Manual address entry must run the same identity and setup-state checks; it cannot bypass them.

## Deployment, server discovery, and disaster recovery

This is the required operator outcome. The scenarios below are **not** claimed as implemented or end-to-end tested. See [Project status](./PROJECT_STATUS.md) and the mandatory release gates in [Release checklist](./RELEASE_CHECKLIST.md).

### Identity and trust model

- **Shop Identity** is the logical shop and its business history. Current source uses `branch_code` as a shop/branch identifier; a separate immutable shop identifier and complete restore lifecycle have not been demonstrated.
- **Server Identity** is the persistent authorized backend identity. Current source has an `instance_id` in an application-data file and advertises it through mDNS and `/discovery/info`. That identity file is separate from the database dump, so copying/restoring database data alone does not prove identity recovery.
- **Machine Identity** is per-installation configuration, not Shop Identity, Server Identity, user role, or authority to write. A replacement client should receive a new Machine Identity and reconnect to the same verified Shop Identity.
- Discovery advertises `_lovely-tech-pos._tcp.local.` and verifies product, identity, protocol/API/app versions, and branch code against `/discovery/info`. An open port (including 8000) is not proof of a genuine server. A client must fail closed on identity/setup-state mismatch.
- Current discovery chooses the first verified candidate. Duplicate-server rejection, exclusive active-writer ownership, and split-brain prevention are not demonstrated. Until implemented and tested, isolate duplicates and do not allow either conflicting instance to accept writes; an Admin must resolve ownership.

### Target guided setup

The same role-aware installer/executable should, where possible, discover and verify an existing shop and offer:

1. **Connect to an existing shop:** resolve automatically with mDNS/DNS-SD, verify product/protocol and persistent identity, then bind the CLIENT to the logical shop identity. A manual address is an Admin-only fallback and undergoes the same checks.
2. **Create a new shop:** only after confirming no existing shop is being accidentally duplicated; guide first Admin creation, unique credentials/secrets, recovery-material custody, server role, and required security controls.
3. **Restore an existing shop:** require Admin authorization and reauthentication, a selected VERIFIED backup, safety backup, explicit confirmation, integrity checks, and reconciliation of Shop Identity and Server Identity before enabling writes.

Ordinary installation should not require entering IP addresses, PostgreSQL credentials, Python/Node settings, database URLs, or manually running migrations. This describes the target experience, not the current scripts: current server setup requires operator-provided environment/database configuration and Alembic invocation, while client packaging and server installation are separate. Do not bypass privilege checks or reveal credentials to achieve easier setup.

### Recovery scenario runbooks

- **Router replaced / server DHCP address changed:** keep the existing server and identity; clients rediscover the address and reconnect automatically. No reinstall or manual IP edit should be necessary. This is unverified on physical LAN hardware.
- **Server laptop failed:** isolate the failed host; install the same application in SERVER role on a replacement; restore the latest VERIFIED backup; restore or safely rebind the existing Shop Identity and authorized Server Identity; run health, schema, integrity and identity checks; permit only one writer; then let clients rediscover. Database-only restore does not currently prove that the external instance identity was recovered. End-to-end recovery is unverified.
- **Client laptop replaced:** install in CLIENT role, assign a new Machine Identity, discover the existing server, verify Shop/Server Identity and setup state, and reconnect without changing server data. Unverified end to end.
- **Server and all clients replaced:** restore the latest VERIFIED copy on one new SERVER, establish one authorized writer and the recovered identity, install every other device as CLIENT, and verify all clients against the same shop before reopening transactions. Unverified end to end.
- **New shop/no database:** use the new-shop path, verify there is no existing shop to connect to or restore, and guide first Admin/security setup. Do not treat bootstrap as recovery. The complete installer wizard is not demonstrated.
- **Owner/Admin laptop is off:** the Cashier server and any remaining clients continue normal LAN transactions. Validate on the target network; this is a topology requirement, not recorded acceptance evidence.
- **No VERIFIED backup:** do not offer restore; preserve current data and report `NO_VERIFIED_BACKUP` with an explicit next action. Never fabricate a recovery point.
- **Restore failure or identity cannot be verified:** keep client writes stopped, preserve the verified safety backup and restore journal, show a recoverable failure state, and require Admin/operator intervention. Never mark the shop READY based only on process startup or database connectivity.
- **Duplicate server/split brain:** isolate both candidates from writes; compare verified Shop/Server Identity and recovery records; an authorized Admin designates one active writer and audits the resolution before clients reconnect. Current source does not enforce this full procedure.

### Offline transactions, backup transport, and upgrades

- A sale committed to the live server database is transaction persistence. An encrypted backup queued for cloud upload is a separate recovery copy; it is not a transaction queue and is not the source of truth for whether a sale committed.
- When server/database and LAN remain healthy, loss of Internet or Google Drive must not discard or roll back committed transactions or block ordinary sales. Backup-at-close policy is separate and may require an available verified local/USB/external/network fallback before Day End or Shift End.
- Current backup code creates and decrypt-verifies local encrypted dumps, records a backup as VERIFIED, and marks a failed Google Drive copy `PENDING_SYNC`. The inspected code has a manual sync endpoint; durable automatic retry scheduling and verification of the uploaded remote object are not demonstrated. Do not claim queued uploads retry automatically until implemented and tested.
- Only VERIFIED backups are restorable. Restore requires Admin reauthentication, explicit confirmation, a verified safety backup, integrity/connectivity checks, identity reconciliation, and an audit/journal record. Availability of backups is limited by actual retention, off-host copies, and recovery-secret custody; do not promise recovery if all usable verified copies or required decryption material are lost.
- For upgrades, first create and verify a recoverable backup. Use a supported integrity-checked package, confirm server/client version compatibility, test migrations on staging, migrate once through the supported server workflow, then verify readiness and identity. Block incompatible client/server pairs with an actionable update message. Preserve Shop Identity and one-writer operation. A supported automatic upgrade/migration flow and rollback guarantees are not demonstrated; do not promise downgrade safety.

## Staging without a spare PC

Use the Owner laptop as a temporary staging host only with synthetic data and an isolated staging database/port:

1. Install into a separate staging environment.
2. Create a database and env file dedicated to staging.
3. Bootstrap fake Admin/Cashier users.
4. Start the staging API on its separate port and run the smoke API and backend test suite.
5. Build and manually accept the client against staging.
6. For two-laptop staging, install the isolated staging server on the Cashier laptop after hours and connect the Owner client over the private LAN.
7. Complete a restore drill and parallel-run comparison before production cutover.

Never wipe or restore a production database as part of staging. Keep the previous business process as source of truth through a controlled parallel run until authorized go-live.

## Backup lifecycle

1. Create a PostgreSQL custom-format dump.
2. Encrypt/authenticate the dump using the configured secret and record integrity metadata.
3. Verify the encrypted output by reading and decrypting it; only verified points are restore candidates.
4. Optionally upload/copy to the configured Google Drive rclone remote. Failed cloud copy remains pending/retryable; local POS operation continues.
5. Keep emergency local backup storage separate from database working files and include it in the host's protected backup plan.

The application settings provide `BACKUP_ROOT`, PostgreSQL utility paths, optional rclone remote/path, and a default policy requiring a verified backup before day close. The actual configured location, permissions, key custody, retention, and off-host copy must be checked on the target system.

## Restore and replacement-server recovery

Restore is destructive and must be operator-controlled:

1. Authenticate as Admin and reauthenticate for the critical action.
2. Select a VERIFIED backup only and confirm its identity/date/metadata.
3. Create a separate encrypted and verified safety backup of the current target database.
4. Require explicit confirmation before replacement.
5. Restore with `pg_restore --clean --if-exists --exit-on-error`.
6. Run an integrity/connectivity check and confirm required migrations/configuration.
7. Record restore/audit events and verify business data, Shop Identity, Server Identity, and single-writer ownership before reopening client access. The current restore endpoint writes a `RESTORE_STARTED` database event before the dump is applied and appends a success/failure line to an external restore journal afterward; the pre-restore database event is not proof of a completed recovery and may be replaced with the restored database contents. It checks PostgreSQL connectivity but does not perform identity-reconciliation or writer-fencing checks; keep the replacement server unavailable for writes until a safe procedure exists.

For a replacement server, the PostgreSQL dump restores the `branches` table (`id`, `code`, `name`, active state), users, business records linked by `branch_id`, and database audit/history rows. It does **not** restore the active `instance_id` file (`C:\ProgramData\LovelyTechPOS\server-data\instance.json` by default), client local storage, or secrets held in server configuration. A historical provisioning audit row can include an instance ID, but no code uses it to rebind the active server identity.

`load_instance_identity()` silently creates a new UUID when the identity file is missing, invalid, unreadable, or has no `instance_id`. A replacement host can therefore advertise a new instance ID after PostgreSQL restore. Restoring/copying the old identity file can instead duplicate that ID if the old host is still online; current code does not detect or fence that condition. Do not treat either behavior as safe recovery.

Bootstrap is not a replacement-server recovery path. If `instance.json` has no `branch_code`, the current `_is_bootstrap_allowed()` database checks are skipped; a restored database may therefore accept bootstrap for another branch code. Do not submit bootstrap against restored data. The appropriate Admin-only identity-recovery/rebinding procedure is not implemented; `RecoveryService` handles account/password recovery, not server identity recovery. Do not permit old and replacement servers to accept writes concurrently. These are code-level limits; no destructive restore was run for this audit.

Backups depend on the encryption secret used when they were created. Losing/changing that secret can make older backups undecryptable. Store recovery material separately with restricted access; never put secret values in this document.

## Troubleshooting

- **Client not discovering server:** verify server readiness, private network profile, mDNS/UDP reachability, firewall rules, server identity, and setup state. Use manual address only as a verified fallback.
- **Client discovers an unexpected server or multiple servers:** stop before accepting transactions and escalate for Admin/operator review. Current clients verify each candidate's TXT record against that candidate's `/discovery/info`, but do not enforce the persisted `server_reference`, reject duplicate branch advertisements, or require Admin approval when the instance ID changes. The first verified candidate wins; this is not an authorized identity-resolution procedure.
- **Client sees setup error after bootstrap:** retain the session, show a recoverable error, and retry discovery/identity verification only. Do not resubmit bootstrap credentials.
- **API unavailable after boot:** run preflight; confirm PostgreSQL service/readiness before starting FastAPI; inspect service logs without exposing credentials.
- **Printer unavailable:** preserve the committed transaction; repair the device path and reprint as a separately audited document event.
- **Backup upload unavailable:** keep the verified local copy, mark remote sync pending, and retry when connectivity returns.
- **Restore fails:** stop client writes, preserve the safety backup and restore journal, inspect the explicit error, and do not claim success based only on process launch.
- **MSI generation fails due missing `light.exe`:** consult current Tauri/Windows prerequisite documentation before enabling optional Windows features; do not change system configuration without authorization.

## References

- [Tauri Windows prerequisites](https://v2.tauri.app/start/prerequisites/)
- [Tauri CLI reference](https://v2.tauri.app/reference/cli/)
- [Rust installation](https://www.rust-lang.org/tools/install)
- [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
- [Microsoft WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/#download-section)
