# Lovely Tech POS — Architecture

## Deployment model

The production topology is a cashier-operated Windows server on the shop LAN and one or more desktop clients:

```text
Cashier laptop (always on)
  PostgreSQL 18 ← FastAPI / SQLAlchemy / Alembic
                         ↑ REST/JSON over private LAN
Owner/Admin and cashier POS clients (React/TypeScript in Tauri)
```

Only the FastAPI service accesses PostgreSQL. Client machines must never receive database credentials or connect directly to PostgreSQL. The Owner/Admin laptop is a client and may be powered off without interrupting POS operations. Normal sales and other core workflows should not depend on Internet access.

## Components

- **Backend (`backend/`)**: Python 3.13 FastAPI service; SQLAlchemy 2.x persistence; Alembic migrations; auth/session and permission dependencies; domain services for sales, FIFO inventory, purchases, returns, repairs, warranty, cash/day, reports, documents, and backup/recovery.
- **Frontend (`frontend/`)**: React and TypeScript application built by Vite. It calls the versioned REST API, persists the authenticated session through the shared client mechanism, and uses discovery/verified identity rather than embedding a fixed shop IP.
- **Desktop (`desktop/tauri/`)**: Tauri 2 shell around the production Vite output at `frontend/dist`. Current configuration targets MSI and NSIS and uses the WebView2 embed bootstrapper.
- **Windows scripts (`scripts/windows/`)**: server installation/preflight/startup/firewall verification, client packaging, staging setup, backup/restore, and acceptance runners.
- **PostgreSQL/Alembic**: UUID-based internal records, fixed-point amounts, branch-scoped operational data, transactional number allocation, inventory movements/lots, audit/history, idempotency, and selected version-lock constraints.

## Startup and server discovery

The client boot flow checks loopback (`127.0.0.1`) to determine whether the local machine is the server, preserves a saved machine role on later launches, and otherwise discovers a server over the LAN. Discovery must validate server identity and setup state; a CLIENT must not enter READY until those checks pass. Manual server entry is an identity-checked fallback, not a bypass for setup-state validation. Bootstrap success must persist the shared authenticated session and refresh discovery before READY. A failed refresh or mismatch must fail closed and permit verification retry without resubmitting bootstrap credentials.

The Windows build script intentionally sets a relative API base and documents runtime mDNS discovery plus identity-checked manual fallback. Actual two-machine name resolution, firewall traversal, address changes, and replacement-server behavior remain acceptance tests rather than architecture assumptions.

## Deployment, server discovery, and identity

The target deployment is one role-aware Lovely Tech POS installer/executable with separate server and client installation paths. Machine role (`SERVER` / `CLIENT`) is installation configuration, independent of the signed-in user role (`ADMIN` / `CASHIER`). The production server is the Cashier laptop; Owner/Admin laptops are clients and can be off without stopping server operations. **Current implementation status:** the inspected Windows server installation/start scripts and Tauri client packaging script are separate; a single role-selectable installer is not demonstrated.

Identity terminology:

- **Shop Identity** is the durable logical shop/business history. The current source exposes `branch_code` as the shop/branch identifier, but a distinct immutable Shop Identity identifier and its full recovery lifecycle are not demonstrated.
- **Shop/Branch persistence:** PostgreSQL stores a `branches` row with a UUID primary key (`branches.id`) and unique `branches.code`; business records link to the branch by `branch_id`. Provisioning also copies the branch code into the server identity JSON file. This does not create a separate immutable Shop Identity.
- **Server Identity:** `instance_id` is stored in `C:\ProgramData\LovelyTechPOS\server-data\instance.json` by default, outside PostgreSQL. The mDNS TXT record and `GET /discovery/info` expose it. A PostgreSQL dump restores branch/business rows and audit history, but not this file or its current authoritative identity. A provisioning audit record may contain the instance ID used at that time; it is historical audit data, not an active identity-recovery mechanism or trusted sidecar.
- **Identity-file loss/corruption:** `load_instance_identity()` generates and writes a new UUID when the file is missing, unreadable, invalid JSON, or lacks `instance_id`. On a replacement host this can create a new Server Identity beside restored PostgreSQL data; copying the old identity file instead can clone the identity if the old server remains active. Neither path is reconciled or fenced automatically.
- **Machine Identity:** `frontend/src/services/machine-config.ts` stores `machine_role`, `client_id`, `server_reference`, and `setup_state` in browser local storage under `ltpos_machine_config`. `client_id` is local to that client; `server_reference` stores a discovered backend `instance_id`. These are client-side configuration, not server-enforced authorization or user identity.

The Tauri client browses `_lovely-tech-pos._tcp.local.`, checks required TXT fields, calls `/discovery/info`, and compares product, instance, protocol/API/app versions, and branch code. This rejects an individual candidate whose TXT identity disagrees with its HTTP response. It does not compare that candidate's instance ID to the previously persisted `server_reference`, and verified manual-server configuration also does not enforce that continuity check. The first matching candidate wins; the resolver does not inspect all candidates for duplicate branch or instance identities. The frontend gates the normal Tauri POS screen on `READY`, but this is not a persistent identity pin or a single-writer guarantee.

Accordingly, two servers can both pass the per-candidate TXT/HTTP comparison while advertising the same `branch_code`; if both are reachable, the first verified result is selected and later candidates are not evaluated. A server with a different valid `instance_id` can also replace the stored `server_reference` on successful client application. No policy rejects duplicate shop advertisements, requires Admin approval for a changed server identity, enforces an exclusive active-writer lease, or prevents split brain. A TXT/HTTP mismatch for the only candidate fails discovery, but a later valid candidate can still be accepted. These are material trust/recovery gaps, not physical LAN test results.

## Recovery and upgrade boundaries

The database backup flow encrypts and verifies local PostgreSQL dumps, marks them VERIFIED, supports Admin-authorized restore with reauthentication, explicit confirmation, a safety backup, integrity/connectivity checks, and restore audit/journal events. It does not export or restore the external instance identity file, create an identity manifest, reconcile the restored branch with a Server Identity, or establish that the previous server is fenced. `RecoveryService` handles account recovery/password reset, not shop/server identity rebinding. The restore endpoint can report PostgreSQL restore success after a connectivity query without performing identity reconciliation; this is not sufficient evidence to reopen a replacement server safely.

There is an additional bootstrap edge case after identity loss: `_is_bootstrap_allowed()` rejects when `instance.json` has a `branch_code`, but its database checks are conditional on that same value. With a missing/new identity file (no `branch_code`) and a restored database, those checks are skipped, so bootstrap can proceed for a different branch code. Startup setup-state reporting is not an identity-recovery gate. Do not run bootstrap on a restored database until this ambiguity is resolved.

The inspected cloud copy path records pending sync on failure and provides a manual sync endpoint; durable automatic retry scheduling and upload-then-remote-verification are not demonstrated. Normal LAN transactions should remain database-backed and independent of Internet; backup upload state is separate.

The intended setup/recovery wizard offers connect to existing shop, create new shop, and restore existing shop. Current application flow does not demonstrate this complete guided installer or all failure scenarios. Requirements and acceptance cases are in [Requirements section 14](./REQUIREMENTS.md#14-deployment-server-discovery-and-disaster-recovery); operational procedures and gaps are in [Operations and recovery](./OPERATIONS_AND_RECOVERY.md#deployment-server-discovery-and-disaster-recovery). Do not infer router-change, all-device replacement, upgrade compatibility, or disaster recovery acceptance from mDNS code or unit tests alone.

## Transaction and data flow

1. The user authenticates to the API. Backend dependencies enforce the user, role, session lifetime, branch scope, and permission for each operation.
2. The frontend sends validated domain requests to REST/JSON endpoints. Financially significant retryable requests carry idempotency keys; mutable versioned records carry expected versions.
3. The backend applies domain rules and database changes transactionally. Inventory effects are movements/lot allocations, and financial calculations use fixed-point values.
4. Audit/document/history events are recorded separately from editable business state. Migration 0030 installs append-only database protection for selected history and recovery tables.
5. The frontend displays the authorized response. Printing is downstream of transaction commit; a print failure cannot undo the sale.
6. Backup and recovery operate on PostgreSQL custom-format dumps, encrypted and verified before they become restore candidates. Optional cloud copy is backup transport only, never database replication.

## Security boundaries

- Backend authorization is authoritative; frontend visibility is not a security control.
- Cashier-facing APIs and reports must not expose supplier/purchase cost, FIFO unit cost, or profit.
- Secrets, database access, and recovery keys are server/operator-controlled.
- The server firewall should restrict the API to trusted private networks. PostgreSQL must not be exposed to clients.
- Keep the idle/absolute session rules, critical reauthentication, branch isolation, and audit protections documented in [Requirements](./REQUIREMENTS.md); resolve any code/config mismatches listed in [Project status](./PROJECT_STATUS.md).

## Build and packaging

The frontend production build outputs to `frontend/dist`. `desktop/tauri/tauri.conf.json` resolves `frontendDist` as `../../frontend/dist`. `scripts/windows/Build-LovelyTechClient.ps1` builds the frontend without baking a shop IP into production output, then runs `cargo tauri build`. It performs a reachability warning only; runtime discovery is used by the packaged app.

## Boundaries and non-goals

- No direct client-to-PostgreSQL connections.
- No Google Drive mounted as a live database volume.
- No cloud dependency for routine LAN POS transactions.
- No hardcoded server address in the distributed client.
- Do not infer that same-installer server/client role switching, historical import, or physical failover is complete unless current implementation and acceptance evidence prove it.
