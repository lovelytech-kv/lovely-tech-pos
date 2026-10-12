# Lovely Tech POS — Release and Acceptance Checklist

Do not mark the release ready until applicable items have evidence recorded for the actual target machines and data. Automated tests do not replace shop acceptance. Mark each item `PASS`, `FAIL`, `BLOCKED`, or `NOT RUN`, with date, version, operator, and evidence location.

## 1. Build and software verification

- [ ] Current Python runtime matches backend metadata (`>=3.13,<3.14`); production dependencies are installed from the intended lock/constraints.
- [ ] `pytest -q` passes on the current source; record count, warnings, and environment.
- [ ] `python -m compileall -q backend/app backend/alembic/versions` passes.
- [ ] Alembic migration chain has one intended head; migration SQL/upgrade has been tested in staging; deployed DB revision is recorded.
- [ ] Focused frontend onboarding/API/discovery tests pass; no assertions are skipped to conceal failures.
- [ ] `npx tsc -b` passes.
- [ ] `npm run build` completes with the real app entry and normal tree-shaking/minification. Confirm Rollup resolves to the pinned 4.43.0 override; do not treat diagnostic output as a release bundle.
- [ ] Playwright smoke and required browser flows pass against a staging server.
- [ ] Tauri Windows build produces the intended signed/unsigned deliverables and launches; record artifact path, size, timestamp, and hash.
- [ ] No unresolved dependency, CSP, secret-scanning, or security review blockers remain.

## 2. Security and authorization

- [ ] Cashier API responses and exports never reveal purchase/supplier cost, FIFO unit cost, profit, internal pricing rationale, or detailed backup/restore records.
- [ ] Backend rejects unauthorized actions regardless of UI visibility; verify permission removal takes effect.
- [ ] Session idle timeout is 30 minutes, absolute lifetime is 12 hours, and critical reauthentication behavior matches the required 10-minute policy.
- [ ] Admin recovery, password reset, forced password change, token revocation, and branch isolation work as specified.
- [ ] Test security-sensitive actions: critical reauthentication, stock/purchase corrections, permission changes, day reopen, backup restore, overrides, and export.
- [ ] Append-only audit/history survives attempted update/delete at database level for protected tables.
- [ ] Secrets are unique per environment, protected from cashier access, absent from bundles/logs/docs, and recoverable where backup decryption requires them.
- [ ] Confirm Windows account privileges, firewall scope, PostgreSQL exposure, disk encryption status, Tauri CSP, and update/patch process.

## 3. LAN, role, and startup

- [ ] The same supported installer/executable offers SERVER and CLIENT installation; machine role is persisted independently of ADMIN/CASHIER user role.
- [ ] Cashier laptop hosts PostgreSQL and FastAPI; owner/client laptop may be powered off without stopping POS operation.
- [ ] Clients never connect directly to PostgreSQL; server firewall allows only the required private-LAN API traffic.
- [ ] Fresh client checks only `127.0.0.1` to determine whether the local machine is the server.
- [ ] Saved machine role is preserved on later launch; client discovers the current server without a hardcoded IP.
- [ ] With a router replacement and with a changed DHCP lease/IP, clients rediscover/reconnect without reinstall or manual address edits.
- [ ] Discovery rejects unrelated services even if port 8000 responds; verify product/protocol, supported API version, setup state, Shop Identity, and authorized Server Identity.
- [ ] Server identity and setup state are checked on discovery and manual address entry; an unverified/mismatched server cannot enter READY.
- [ ] Bootstrap persists the session and refreshes verified discovery before READY. Failed verification is retryable without resubmitting bootstrap.
- [ ] Multiple servers advertising one Shop Identity fail closed for writes; prove the authorized Admin resolution restores exactly one active writer and produces an audit record.
- [ ] Server starts after reboot only when PostgreSQL is ready; test service recovery and client reconnect.
- [ ] Test DHCP/address change, DNS/mDNS, firewall, LAN interruption, concurrent client access, and replacement-server identity/recovery.
- [ ] Core workflows continue with Internet disconnected.
- [ ] With the Owner/Admin laptop powered off, complete normal cashier-server and remaining-client LAN workflows.
- [ ] Guided setup detects an existing shop where possible and supports verified connect-existing, create-new (including first Admin/security setup), and restore-existing paths without asking ordinary operators for IP, DB credentials/URLs, runtime configuration, or manual migrations.

## 4. Sales, inventory, and finance

- [ ] Cash, Card, Online, split payments, typed prices, discount authority/approval, and Admin-only credit sale are tested.
- [ ] Invoice numbers are atomic and never reused; duplicate-click and timeout retry create one transaction.
- [ ] Printer failure after commit does not roll back sale; reprint records a separate document event.
- [ ] FIFO is exact under multiple lots, negative stock, subsequent purchases, corrections, returns, repairs, and concurrency.
- [ ] Negative-stock reconciliation is deterministic and later purchases retain full lot quantity/cost.
- [ ] Purchase cost/date/quantity/reference corrections are authorized, version-checked, audited, and replay FIFO safely.
- [ ] Partial returns, seven-day window/Admin override, GOOD lineage restoration, damaged loss, refunds, return charges, and exchange accounting reconcile.
- [ ] Purchase entry keeps cost private from Cashier; pending Admin cost completion creates correct lots.
- [ ] Repair advance/final/split payments, FIFO parts, GOOD part returns, damage review, delivery override, cancellation, and immutable payment history work.
- [ ] Warranty dates/statuses, all supported rule types, claims, rejection, supplier replacement, damage outcome, exception registration, lost-bill recovery, and sale-time snapshots work.
- [ ] Day Start denominations, Shift End vs Day End, Continue Today/auto-close, Admin reopen, one reload per day, Day-End differences, expenses/other-income approval, Cash Drawer, and Cash In Hands reconcile.
- [ ] Customer history, credit/repair settlements, proof, reprints, reports, target snapshots, and PDF/Excel exports are role-appropriate and correct.

## 5. Backup, restore, and data migration

- [ ] Backup lifecycle is recorded; only VERIFIED backups are restore candidates.
- [ ] Backup encryption/integrity verification succeeds; recovery key custody and offline recovery are proven.
- [ ] Emergency local backup is physically/logically separate from database working files.
- [ ] Separate committed local database transactions from encrypted backup copies awaiting upload; simulate cloud loss and prove committed sales persist and ordinary LAN sales continue while the local server/database/LAN remain healthy.
- [ ] Interrupt upload/connectivity, prove queued cloud copies retry after connectivity returns, and verify the uploaded remote copy before marking sync complete.
- [ ] Restore flow enforces Admin reauthentication, safety backup, explicit confirmation, selected verified point, post-restore integrity, and immutable audit event.
- [ ] With no VERIFIED backup, failed restore, unavailable recovery secret, or unverified identity, fail safely, preserve available data/safety copies, show explicit state, and keep writes disabled.
- [ ] Replace only the server laptop: restore the latest VERIFIED backup, reconcile the existing Shop Identity and authorized Server Identity, verify schema/data/readiness, and reconnect clients without duplicate shop creation.
- [ ] Replace only a client laptop: assign a new Machine Identity and reconnect to the same verified shop without altering business data.
- [ ] Replace server and all client laptops: restore one active server, install new clients, and verify all clients see the same logical Shop Identity.
- [ ] Perform restore on an isolated replacement server and prove duplicate-server/split-brain safeguards prevent simultaneous writers.
- [ ] Complete historical spreadsheet import with Admin preview/approval, provenance, duplicate handling, and financial/stock reconciliation before go-live.

## 6. Windows hardware and operations

- [ ] Verify actual Rust stable/Cargo, Tauri CLI, Microsoft C++ Build Tools, and WebView2 prerequisites.
- [ ] Install and launch the actual Tauri package on target Windows machines; verify app restart, update, and uninstall behavior.
- [ ] USB barcode scanner input is correct for supported item/serial flows.
- [ ] ESC/POS receipt and A5 warranty printers work; unplug/reconnect does not corrupt transactions.
- [ ] Reboot after installation and verify PostgreSQL/API startup, readiness, logs, and backup schedules.
- [ ] Document operator procedures, escalation, recovery contact, data retention, and supported upgrade path.
- [ ] Upgrade from a supported prior client/server version on staging: verify package integrity, version compatibility, pre-upgrade VERIFIED backup, migration checks, preserved Shop Identity/business data, one-time migration, readiness, audit record, and safe blocked behavior for incompatible client/server versions.

## 7. Go-live authorization

- [ ] Use synthetic data in staging; complete the acceptance matrix before production install.
- [ ] Run an authorized parallel period with the prior process remaining source of truth.
- [ ] Verify a recent encrypted backup and successful restore drill before cutover.
- [ ] Obtain Admin/owner sign-off for data reconciliation, permissions, security, operations, and recovery.
- [ ] Archive the tested build identity, source revision, dependency versions, migration revision, configuration template, test logs, artifact hashes, and release checklist.
- [ ] Confirm the project is not described as production-ready while any mandatory item is `FAIL`, `BLOCKED`, or `NOT RUN`.
