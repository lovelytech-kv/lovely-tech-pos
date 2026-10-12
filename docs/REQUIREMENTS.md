# Lovely Tech POS — Canonical Requirements

This document records the agreed product scope. It is normative: implementation status is tracked separately in [PROJECT_STATUS.md](./PROJECT_STATUS.md), and release evidence is tracked in [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md).

## 1. Architecture and technical boundaries

- Use PostgreSQL 18, Python 3.13, FastAPI, SQLAlchemy 2.x, Alembic, React, TypeScript, Vite, and Tauri 2. Communicate through REST/JSON over the local network.
- All database access is server-side through FastAPI. Client applications must never connect directly to PostgreSQL.
- Use UUIDs for internal identities and backend-allocated human-readable document numbers. Number allocation must be atomic and invoice numbers must never be reused.
- Represent money with Python `Decimal` and PostgreSQL fixed-point `DECIMAL`/`NUMERIC`, never binary floating point.
- Inventory is movement- and lot-based. Cost of goods sold follows exact FIFO, including deterministic handling and reconciliation of negative stock.
- Enforce permissions and data visibility on the backend. Hiding controls in the UI is not an authorization boundary.
- Preserve audit and business-history records as append-only. Important transactions must not be hard-deleted.
- Use idempotency keys for retryable financial mutations, concurrency/version checks for controlled edits, and branch isolation for business data.
- Integrate local printers without making transaction success depend on printer availability.
- Support encrypted local backups and optional Google Drive backup storage. Google Drive availability must not be required for ordinary LAN POS operation.
- Use Pytest for backend regression tests and Playwright for browser acceptance tests.
- The Cashier laptop is the always-on production server (PostgreSQL plus FastAPI). The Owner/Admin laptop is a client and may be turned off without interrupting POS operations.
- The same supported Lovely Tech POS installer/executable must offer server or client installation. Machine role (`SERVER` / `CLIENT`) is independent of authenticated user role (`ADMIN` / `CASHIER`).
- Clients must automatically discover and reconnect to the legitimate server without hardcoded LAN IP addresses. Router replacement and DHCP/IP changes must not require reinstalling the app or manually editing IP addresses.
- A discovered endpoint is trusted only after product/protocol and persistent identity verification; an open port, including port 8000, is not proof of a genuine server.
- Replacement-server recovery must restore the latest VERIFIED backup with minimal manual configuration and preserve the existing logical shop identity. See the detailed requirements in section 14.
- Normal installation and operation must not depend on Git.

## 2. Security, sessions, and role permissions

- Cashiers must never access purchase/supplier cost, FIFO unit cost, profit, internal pricing rationale, or detailed backup/restore information. Enforce this in API permissions, response schemas, and queries as appropriate—not only by hiding UI.
- Required session controls: 30-minute idle timeout, 12-hour absolute lifetime, and a 10-minute critical reauthentication window. Reauthentication must verify the relevant user's password and be scoped to authorized critical actions.
- Preserve existing RBAC, branch isolation, Admin recovery controls, and permission revocation behavior.
- Record security-sensitive and financial actions in the append-only audit/history system, including Admin approvals, overrides, corrections, reprints, backup/restore, and recovery.
- Apply stable idempotency keys to retryable create/payment/refund/settlement actions. Replaying an identical request must not create duplicate financial movements; conflicting payloads under the same key must be rejected.
- Protect mutable records with optimistic version checks and transactional locking where concurrent updates could violate business or financial invariants.
- Do not claim full security, operating-system hardening, disk encryption, or recovery guarantees without direct evidence and acceptance testing.

## 3. Sales, payments, and documents

- Support Cash, Card, Online, and split payments.
- Permit typed sale prices, with configurable cashier discount limits and Admin approval/override for amounts beyond authority.
- Credit sales are Admin-only.
- Assign invoice numbers atomically and never reuse them.
- Commit the sale before printing. Printer failure must not roll back a committed sale.
- Reprinting is a separate document event with an audit trail.
- Customer-facing invoices, receipts, and other customer-facing documents show the final selling price only; never show buy cost, FIFO cost, profit, or internal pricing rationale.
- Duplicate clicks, request timeouts, and safe retries must not create duplicate sales or payments.
- Preserve sale-time price, discount, payment, customer, invoice, and warranty snapshots needed for historical documents and reports.

## 4. Inventory and FIFO

- Track inventory through movements and purchase lots; calculate cost using exact FIFO.
- Negative stock may be allowed only with a clear warning and deterministic later reconciliation. A later purchase retains its full original quantity and cost.
- Reconcile negative allocations deterministically without changing historical purchase-lot identity or quantity.
- Audit purchase cost, date, quantity, and reference corrections, and recalculate affected FIFO allocations and dependent costs correctly.
- Preserve original stock lineage for valid returns and reversals. Damage/loss must be represented explicitly rather than silently returned to saleable stock.

## 5. Returns, exchanges, and purchases

- The normal return window is 7 days. Beyond-authority returns require an authorized Admin override. Support partial returns.
- GOOD returns restore the original stock lineage. Damaged returns route to Damage/Loss.
- Return charges are separate income/profit entries. An exchange is a separate return plus a separate new sale; refund and payment accounting must remain correct.
- Cashiers may enter purchase items and quantities without seeing cost. Admins have a private pending-cost workflow; completed costs create purchase lots.
- Corrections to completed purchases are audited and must obey concurrency checks and FIFO lineage safety.

## 6. Repairs

- Supported repair statuses are `RECEIVED`, `CHECKING`, `WAITING FOR CUSTOMER`, `WAITING FOR PART`, `REPAIRING`, `READY`, `DELIVERED`, `RETURNED TO CUSTOMER`, and `CANCELLED`. Preserve status history; do not remove or rename statuses.
- Provide a repair intake form, labour-only charges, FIFO part consumption, and original-lineage restoration when an unused GOOD part is returned.
- Route damaged parts to Damage Review/Admin.
- Support advances, final payments, outstanding balances, Cash/Card/Online/split payment, and an Admin delivery override.
- Cancellation reverses stock effects safely while preserving immutable payment history.
- Preserve repair references, estimates/final charges, customer and device details, status history, and printable/reprintable records.

## 7. Warranty

- Warranty begins on the sale date and stores exact expiry/status plus any authorized sale-time override.
- Support NONE, DAYS, MONTHS, CHECKING ONLY, and CUSTOM rules.
- Warranty claims are separate from repairs. Cashiers may create claims; Admins decide supplier, damage, replacement, and other permitted outcomes.
- Supplier replacement is recorded as `WARRANTY_REPLACEMENT`, not as a purchase.
- Support rejection paths, exception-only manual registration, lost-bill recovery, and audited reprints.
- Preserve immutable sale-time warranty snapshots so later product-default changes do not rewrite a completed sale's warranty.

## 8. Cash and business day

- Opening denominations are 5000, 2000, 1000, 500, 100, 50, and 20.
- Cash Drawer = opening + drawer inflows − refunds/outflows + Day-End reload.
- Cash In Hands = all approved shop inflows − all shop outflows, including every payment method.
- Expenses and purchases affect Cash In Hands but do not automatically reduce the physical Day-End drawer.
- Shift End is distinct from Day End.
- After Cashier Shift End, Admin has approximately one hour to Continue Today; otherwise the business day auto-closes. Admin reopening is permission-controlled and audited.
- Reload is one entry per day, brand-wise, cash-only, and Day-End related.
- Day End requires denomination reconciliation and a reason for any difference.

## 9. Expenses, other income, customers, and settlements

- Cashier-entered expenses and other income remain Pending Approval and are excluded from final Profit/Cash In Hands until approved.
- Admin approve/reject actions are audited; Admin may add categories.
- Customer details are optional where permitted. Customer history should include sales, repairs, warranty claims, bills, and settlements, subject to role-specific privacy.
- Credit sales are Admin-only.
- Repair balance settlements are payment events, not new revenue. Preserve settlement proof and reprint history.

## 10. Reports and targets

- Provide Daily, Monthly, Yearly, and Custom reporting for Sales, Profit, Stock, Purchase, Repair, Warranty, Cash Drawer, and Cash In Hands.
- Include payment splits, previous-month comparison, and PDF/Excel export where supported.
- Support targets for Sales Amount, Item Sales Profit, Repair Income, Repair Profit, Bills Count, and Items Sold Count.
- Cashiers must not see numeric profit targets. Progress may exceed 100%; visual bars may cap at 100%. Retain target history as immutable period snapshots.

## 11. Backup and disaster recovery

- Track the backup lifecycle as CREATED → ENCRYPTED → UPLOADED → VERIFIED, with explicit failure/pending states where necessary.
- Only VERIFIED backups may be restored.
- Restore sequence: Admin reauthentication → verified safety backup → explicit confirmation → selected verified restore point → integrity check → audit event.
- Queue and retry backup uploads after connectivity returns; recovery design must avoid split brain.
- Store emergency local backups separately from the database working directory.
- Cashier Shift End and Day End require a successfully verified backup. Retry a failed network backup; if the network target remains unavailable, use a separately configured local, USB, external, or network fallback target and verify the backup there before allowing close. Queue any deferred Google Drive upload for retry when connectivity returns.
- Google Drive is optional backup/recovery storage; normal LAN POS operation must remain available without cloud access.
- Protect and document the recovery key/secret. Losing or changing the key must not be represented as harmless if it makes old backups undecryptable.

## 12. Historical data import

- Support controlled import of products, purchase history, sales history, and customer/history from spreadsheets.
- Required workflow: staging → validation → mapping → duplicate detection → business-rule validation → Admin preview → approved import → PostgreSQL write → verification/reconciliation.
- Preserve original dates, references/invoices, quantities, costs/prices, customer/payment data where available, and provenance.
- Never fabricate missing historical records; unresolved data must be reported for human disposition.
- Reconcile opening stock + historical purchases − historical sales + returns/adjustments against current stock.
- Complete and approve historical import before final release/real-shop acceptance.

## 13. Accessibility, resilience, and release quality

- Provide clear validation, confirmation, timeout, connectivity, and recovery errors without disclosing credentials, tokens, or secrets.
- Protect irreversible and financially significant actions with explicit authority, confirmation, audit, and idempotency as appropriate.
- Keep core LAN operations independent of Internet connectivity.
- Automated tests, type checking, packaging, and physical/shop acceptance are distinct gates; passing one does not imply the others.

## 14. Deployment, server discovery, and disaster recovery

These are normative product requirements, not statements that the current deployment or recovery workflow has passed implementation or acceptance.

### Installer, roles, and topology

- The same supported Lovely Tech POS installer/executable must guide installation as either a server or client. Server installation places PostgreSQL and FastAPI on the always-on Cashier laptop; clients call FastAPI over the private LAN and never connect directly to PostgreSQL.
- Machine role (`SERVER` / `CLIENT`) describes installation topology and is independent of the signed-in person's user role (`ADMIN` / `CASHIER`). A user changing does not change a machine's configured role.
- Owner/Admin client laptops may be switched off without stopping the Cashier server or interrupting operations on other clients.
- Installation and upgrades must not require the operator to manually enter IPs, PostgreSQL credentials, Python/Node settings, database URLs, connection strings, or run migrations. The guided application performs supported checks and presents actionable, non-secret errors; privileged service setup remains protected.

### Logical shop, server, and machine identity

- **Shop Identity** identifies the logical shop and its business history and remains stable across router changes, machine replacement, and a verified restore.
- **Server Identity** identifies the active server installation authorized to serve that shop. It is persistent across ordinary restarts and is associated with exactly one Shop Identity and one active writer.
- **Machine Identity** identifies a particular physical/software installation for local configuration and diagnostics. It is not the Shop Identity, the user identity, or authorization to serve as the shop's active writer. Replacing a client creates a new Machine Identity without creating a new shop.
- A restored database must be reconciled with its Shop Identity and the authorized Server Identity before it is advertised for client writes. Backup/restore must preserve or safely rebind logical identity; it must not silently create a second shop or trust an unverified replacement identity.
- Clients bind to the verified logical Shop Identity and authorized Server Identity, not permanently to an IP address. Addresses are transient discovery results.
- Conflicting identity, more than one server claiming the same active Shop Identity, or evidence of split brain must fail closed for writes. Keep the conflicting server isolated until an authorized Admin resolves identity and single-writer ownership. Never merge independent writable databases automatically.

### Zero-IP discovery and trust

- Clients discover the service automatically over the LAN using the supported Lovely Tech POS discovery protocol and reconnect when the server's address changes.
- Verify the product, supported protocol/API version, setup state, and persistent identity through the service advertisement and the server's discovery endpoint. A responding host or open port alone is insufficient.
- Reject mismatched, incomplete, unsupported, or ambiguous identities. Do not allow an unverified server to become READY. Manual address entry, when offered as an Admin-controlled fallback, must apply the same identity, version, setup-state, and Shop Identity checks and must not become the normal configuration path.
- Keep mDNS/DNS-SD discovery and any manual fallback free of hardcoded LAN IPs. Address changes must update resolution without changing logical identity.

### Guided setup and recovery choices

- On installation, detect a verified existing Lovely Tech POS shop/server where possible and offer clear, authorized paths to **connect to an existing shop**, **create a new shop**, or **restore an existing shop**.
- Creating a shop guides the operator through first Admin creation and mandatory security choices (unique credentials/secrets, recovery material custody, and protected server configuration). Never display or log passwords, tokens, database credentials, or secret values.
- Recovery, server ownership/identity changes, restore, and privileged machine configuration are Admin-only and require the required critical reauthentication and audit event. Cashiers do not receive recovery or privileged configuration controls.
- The wizard must not ask ordinary operators to configure IP addresses, PostgreSQL credentials, Python/Node runtimes, database URLs, or manually invoke migrations. If a prerequisite or recovery check fails, stop before writes and explain the safe next step without exposing secrets.

### Required recovery scenarios and safe outcomes

Document, implement, and acceptance-test all of these scenarios:

1. Router replacement or server DHCP/IP change: clients rediscover and reconnect without reinstall or manual address editing.
2. Server laptop failure: install the same application on a replacement server, restore the latest VERIFIED backup, validate/reconcile Shop and Server Identity, then allow clients to reconnect.
3. Client laptop replacement: install as CLIENT, discover and verify the existing shop, and preserve the server and business history.
4. Server and all clients replaced: restore the shop on the new server, establish one authorized writer, install new clients, and verify each against the recovered logical shop.
5. New shop with no existing database: guided new-shop setup creates the first Admin and performs required security setup without presenting itself as a restore.
6. Owner/Admin laptop off: cashier server and remaining clients continue normal LAN operation.
7. No VERIFIED backup, failed restore/integrity check, unknown recovery key, identity mismatch, duplicate active server, or unresolved split brain: do not report recovery success or permit writes on an unverified instance; preserve available data/safety copies, record the failure, and give an explicit recovery state and Admin/operator next step.

Only claim a scenario is implemented or tested when source, automated tests, and/or recorded target-machine acceptance evidence support that claim. A script, UI path, backup file, or mocked test alone is not end-to-end recovery evidence.

### Offline transactions, backup queue, and restore controls

- When the local server/database and LAN are operational, local POS transactions must commit without Internet or cloud access. A cloud backup outage must not silently discard or reverse a committed sale and must not unnecessarily block ordinary sales.
- Distinguish transaction persistence from backup transport: a committed transaction is durably recorded by the server database; a backup queue is a separate encrypted recovery copy awaiting upload and verification. Queue state is not a transaction log and does not mean the transaction is absent from the database.
- Keep each local backup encrypted and integrity-verified. Queue failed cloud uploads durably and retry when connectivity returns; mark the remote copy complete only after upload and verification. Preserve the local verified backup and clearly surface pending/failed sync state.
- Only backups in `VERIFIED` state are restore candidates. Restore is Admin-only and requires critical reauthentication, a verified safety backup of the current target, explicit confirmation, selected verified restore point, post-restore integrity and identity checks, and immutable audit/history.
- Do not promise recovery beyond the retained verified backup set and available decryption/recovery material. Loss of the server and all usable verified copies, or loss of the required decryption secret, may make data unrecoverable; state this limitation plainly.

### Upgrade and compatibility safety

- Provide a supported, signed or otherwise integrity-checked application upgrade path that preserves Shop Identity and business data. Keep client/server protocol and API compatibility explicit; block incompatible clients or servers with a clear update path rather than silently connecting.
- Before upgrade, confirm a recent VERIFIED backup and recovery material availability. Check package compatibility and migration preconditions, apply supported migrations once through the server workflow, verify health/readiness and identity afterward, and audit the result.
- Test upgrades and migration rollback/recovery against staging copies first. Never require an ordinary operator to run SQL or migrations manually; do not promise downgrade safety where a migration is not reversible.
- Upgrade, recovery, and server reassignment must preserve one active writer and must not reset Shop Identity.
