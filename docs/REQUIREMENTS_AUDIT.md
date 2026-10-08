# Lovely Tech POS — Full Requirements Audit

Source of truth: `Lovely_Tech_POS_Final_Requirements_v2.0.pdf` and `Lovely_Tech_POS_Database_Technical_Blueprint_v2.0.pdf`.

Legend: 🟢 Complete in source; 🟡 Partial / implementation exists but a locked rule, UX, or acceptance path is incomplete; 🔴 Missing.

## 01 Architecture / Security
- 🟡 Offline-first LAN PostgreSQL/FastAPI architecture — code/deployment scripts exist, but live LAN verification is not possible in this environment.
- 🟢 Branch-aware architecture and Google Drive treated as backup/recovery rather than live DB sync.
- 🟢 UUID internal primary keys and separate human-facing numbering.
- 🟢 Atomic sequential numbering with non-reuse behavior.
- 🟢 Admin/Cashier roles and server-side permission checks.
- 🟢 Role-specific inactivity auto-lock (Admin 5 min / Cashier 60 min) plus absolute session lifetime.
- 🟢 Cashier reset requires Admin verification; forced password change is server controlled.
- 🟢 Admin one-time offline recovery code and session revocation/audit.
- 🟢 Critical Admin re-authentication is now enforced for permission changes, stock adjustment, purchase corrections, day opening/reopen, and database restore when enabled.
- 🟡 Immutable audit — append-only application behavior exists, but database-level protection/triggers are not complete.
- 🟢 User-specific Cashier discount percentage limit plus Admin approval/execution path for excess discounts.

## 02 UI / Navigation / Validation
- 🟢 Separate functional tabs for Dashboard, Sales, Returns, Repairs, Warranty, Stock, Purchases, Expenses, Cash/Day, Reports, Documents, Admin and Backup.
- 🟢 Red/black glass-morphism styling baseline.
- 🟢 Search covers item code/description/brand/model/barcode and Stock now exposes unified serial/IMEI lookup; in-stock-first ordering remains a runtime/UX acceptance item.
- 🟢 Double-click protection exists on sale submission; processing states exist on major actions.
- 🟡 Frontend is broad functional UI but not yet verified by a real Vite build or Playwright runtime in this environment.

## 03 Item Master
- 🟢 Sequential item codes such as LVT0001; numbers are not reused.
- 🟢 Admin-controlled item-code preservation is supported on item creation; auto numbering remains default.
- 🟢 Dynamic Category 1/2 structure and dynamic Item Types in DB.
- 🟢 Multiple barcodes.
- 🟢 Variant storage and Admin item variant creation support quality/compatibility attributes.
- 🟢 Optional master sale price and sale-time custom price.
- 🟢 Historical sale lines store actual sale price/discount.
- 🟢 Serialized item model and duplicate active serial protection at sale time.
- 🟢 Compatible repair parts / display quality variants — Variant model and Admin Item Master variant/compatibility entry UI are implemented; runtime workflow remains to be accepted on Windows.
- 🟢 Sale-time warranty records preserve the default at transaction time for supported standard durations.
- 🟡 CUSTOM warranty rules are supported by the calculator but not fully propagated through sale warranty creation.

## 04 Inventory / FIFO
- 🟢 Movement-based inventory foundation.
- 🟢 Purchase lots separated by date/cost.
- 🟢 FIFO allocation and negative-stock warning/reconciliation foundation.
- 🟢 Later purchases retain original lot quantity/cost while unresolved negative allocations reconcile deterministically.
- 🟢 Positive physical stock corrections use the latest available purchase-lot cost as an adjustment FIFO cost pool; negative corrections use FIFO consumption.
- 🟢 Purchase cost correction and affected sale/repair cost recalculation are implemented with FIFO lineage safeguards and tests.
- 🟢 Purchase date correction with conservative FIFO replay is implemented with explicit refusal when non-purchase positive lineage makes replay unsafe.
- 🟢 Purchase quantity correction is implemented with consumed-quantity protection and dependent FIFO cost recalculation.
- 🟢 Return lineage restoration foundation.
- 🟢 Stock-age-by-purchase-batch endpoint and Stock tab view are implemented.

## 05 Sales / Payments
- 🟢 New Sale flow, cart, quantity, price, discount, total, payment and document type.
- 🟢 Invoice numbering/non-reuse.
- 🟢 Cash/Card/Online and split payments.
- 🟢 Hidden buy cost/profit from cashier-facing sale response/UI.
- 🟢 Admin-only credit sale with customer reference and outstanding calculation foundation.
- 🟢 Cashier discount limit is enforced server-side and excess discounts create Admin approval requests.
- 🟢 Printer failure is outside transaction commit path; completed sale remains valid.
- 🟢 Idempotency key protection.
- 🟢 Serialized/IMEI sale selection UX — Stock serial/IMEI lookup and direct serialized-unit picker inside the normal POS cart are implemented; runtime scanner/hardware acceptance remains environmental.

## 06 Returns / Exchange
- 🟢 7-day normal return rule and Admin override guard.
- 🟢 Partial return validation.
- 🟢 Refund payment ledger with exact refund ceiling.
- 🟢 Return charge as separate income and report component.
- 🟢 Good-return lineage restoration foundation.
- 🟢 Damaged returns no longer perform a second FIFO stock consumption; the original sale cost remains recognized as loss.
- 🟢 Exchange links independent return + replacement sale and prevents original-sale self-linking.
- 🟢 Exchange UI now displays the calculated replacement-sale difference after completion; physical payment/proof behavior remains subject to runtime acceptance.
- 🟢 Important records are not hard-deleted by transaction workflows.

## 07 Purchases
- 🟢 Cashier purchase entry does not expose cost.
- 🟢 Stock increases immediately from purchase entry.
- 🟢 Admin pending-cost queue and item-level cost completion.
- 🟢 Supplier is optional and payment method is not part of purchase entry.
- 🟢 Completed lots preserve cost lineage.
- 🟢 Admin pending-cost UI now exposes quantity/date correction actions with Admin re-authentication; reference editing remains an API-level correction path.

## 08 Repairs
- 🟢 Repair numbering and locked status state machine.
- 🟢 Required historical shop-form fields are represented in the repair model/UI.
- 🟢 Estimate vs final amount and separate labour amount.
- 🟢 FIFO part usage and repair payments.
- 🟢 Delivery outstanding-balance Admin override.
- 🟢 Cancellation keeps payment history and restores good-used parts.
- 🟢 Repair part removal supports Good return and Damaged Review Pending with Admin review.
- 🟢 Repair payments and credit settlements receive human-facing REC numbers and document reprint events.
- 🟢 Repair detail UI now exposes the repair-warranty status/date lookup; full print-layout acceptance remains runtime work.

## 09 Warranty
- 🟢 Product warranty start/expiry/status calculator foundation.
- 🟢 Warranty claim separate from repair.
- 🟢 Cashier claim creation and Admin supplier/damage decision paths.
- 🟢 Supplier replacement is represented as WARRANTY_REPLACEMENT rather than purchase.
- 🟢 Supplier outcome supports replacement, shop-held damage, and customer-keeps-item outcomes.
- 🟢 Admin-only manual warranty exception registration API/UI is implemented with unique branch reference.
- 🟢 Lost-bill recovery search foundation and reprint events.
- 🟢 IMEI/serial warranty lookup is surfaced in the Warranty UI with visible lookup results; runtime warranty acceptance remains environmental.

## 10 Cash / Day
- 🟢 Opening denomination validation with locked denominations.
- 🟢 Cash Drawer calculation separates Card/Online.
- 🟢 Other Cash In and Day-End Reload foundations.
- 🟢 Shift End / Continue Today Business and lazy one-hour auto-close logic.
- 🟢 Admin-only closed-day reopen path is exposed in Cash/Day UI with re-authentication.
- 🟢 Day-End expected/actual/difference/reason validation.
- 🟢 Admin missed/backdated sale date-time is exposed in the Sale UI; mismatch recovery remains subject to live Day-End acceptance.
- 🟢 Separate Admin Cash In Hands calculation/report is implemented.

## 11 Expenses / Other Income
- 🟢 Required system expense categories exist in seed/design.
- 🟢 Cashier entries become Pending Approval.
- 🟢 Pending entries excluded from final profit/Cash In Hands calculations where implemented.
- 🟢 Admin approval/rejection UI and audit foundation.
- 🟢 Admin category and item-type management UI is implemented.
- 🟢 Admin corrections preserve history rather than hard-delete.

## 12 Customers / Credit / Settlements
- 🟢 Customer model and credit-settlement ledger exist.
- 🟢 Credit sale is Admin-only.
- 🟢 Credit settlement records previous/remaining outstanding and is not new revenue.
- 🟢 Repair payment ledger supports settlement-like payments.
- 🟢 Customer search/history and credit-sale selection UI are implemented; Admin can also record credit settlements.
- 🟢 Settlement receipt numbers and document reprint search are implemented.

## 13 Reports / Targets
- 🟢 Daily/monthly/custom date range sales summary foundation.
- 🟢 Sales totals split Cash/Card/Online and combined.
- 🟢 Admin cashier summary with generated gross profit.
- 🟢 Target types and >100% progress display behavior.
- 🟢 Previous-period comparison chart bars are implemented in Reports.
- 🟢 Separate Purchase/Repair/Warranty/Cash Drawer/Cash In Hands report endpoints are implemented.
- 🟢 Sales PDF/Excel export is implemented; browser download requires frontend runtime verification.
- 🟢 Target records now have a dedicated Admin progress-history view using the existing progress service; immutable historical snapshots remain outside the current target model.

## 14 Backup / Restore / Recovery
- 🟢 Real PostgreSQL custom-format dump + encrypted/verified backup envelope.
- 🟢 Only VERIFIED points are selectable.
- 🟢 Separate backup root configuration and safety-backup runner.
- 🟢 Restore runner has explicit confirmation, safety backup and post-restore connectivity check.
- 🟢 Verified restore endpoint now performs safety-backup → pg_restore → post-restore SELECT 1 when explicitly confirmed; persistent journal is kept outside the restored DB.
- 🟢 Optional Google Drive sync is implemented through configured rclone remote, with SYNCED/PENDING_SYNC states and retry endpoint; real Drive credentials are not available here.
- 🟡 Backup interruption/restore interruption have automated runner coverage but cannot be physically tested here.

## 15 Audit / Financial Rules / Acceptance
- 🟢 Core sale/payment/FIFO atomic transaction path.
- 🟢 Audit coverage across major workflows.
- 🟢 Profit formula foundation for sales, returns, repair/other income and expenses.
- 🟢 Payment method does not change FIFO profit.
- 🟢 Credit/repair settlements are payment events.
- 🟢 Cash In Hands and the major report domains are implemented; live financial acceptance remains environmental.
- 🟡 Concurrent edit/version protection exists for selected masters but is not universal across every editable transaction.
- 🟡 Acceptance tests cover many failure cases but not the complete locked matrix.
- 🔴 Real Windows/LAN/Tauri/barcode-scanner/thermal/A5/Google-Drive acceptance cannot be claimed in this environment.

## 16 Database Blueprint Cross-check
- 🟢 All major blueprint data-domain tables are present in migrations/models.
- 🟢 Migration chain was audited and broken revision/index references in the handover were corrected; current head is 0023_history_immutability.
- 🟢 Money columns use fixed-point DECIMAL/Numeric rather than float.
- 🟢 Required unique/index foundations are present for invoice, item code, serial, approval action and idempotency.
- 🟢 Manual warranty reference uniqueness is enforced per branch by database constraint `uq_manual_warranty_branch_reference`.
- 🟡 Server-side state transitions exist for Repair but not all business state machines have explicit transition services.
- 🟡 Audit is application append-only, not DB-trigger protected.
- 🟢 UUID + human-number separation and branch-aware keys are implemented.
- 🟢 Backup/restore execution and optional rclone-based Google Drive sync are implemented; configured credentials and interruption behavior remain environmental acceptance items.

## Audit conclusion before completion work
The uploaded handover is a strong backend foundation and now has **65 passing backend tests**. The remaining work is concentrated in environment-dependent acceptance and a small number of explicit hardening/design items rather than the major transaction workflows.


## Post-audit implementation result
The completion batch implemented the major 🟡/🔴 backend gaps identified above: discount limits/approvals, purchase quantity/reference controls, positive-adjustment FIFO cost pools, repair part removal/damage review, manual warranty registration and supplier outcomes, Cash In Hands and report domains, PDF/XLSX sales export, customer history/credit settlement UI, receipt numbering/reprint, optional Google Drive sync, verified restore execution, critical re-authentication, target >100% percentage handling, and migration-chain hardening.

Remaining verification constraints are environmental rather than intentionally skipped business logic: PostgreSQL/LAN runtime, two-Windows-client concurrency, real thermal/A5 printers, USB barcode scanner, Google Drive credentials, and the production browser dependency install could not be executed in this isolated handover environment. Those are explicitly marked as **UNVERIFIED**, not passed by assumption.

## Additional completion batch — 2026-09-25
- Report exports were extended from the previously supported Sales/Cash-In-Hands set to Purchases, Repairs, Warranty and Cash Drawer, with Admin-only protection where exported data can expose cost/cash-sensitive information.
- Admin Item Master now has create/edit controls, master selection and barcode entry.
- Admin can add categories and item types from the UI.
- Backup UI now exposes verify and Google Drive sync/retry operations in addition to create/restore.
- Backend verification after this batch: 51 passed; Python compile check passed.
- Frontend build remains UNVERIFIED due missing installable npm dependency environment.


## V42 follow-up audit — 2026-09-26
- Serialized sale selection, customer creation, richer repair finalization, warranty lookup/claim notes, target progress history, and Documents/Reprint UI were completed.
- The previously missing DocumentsTab compile defect was fixed.
- Settlement reprint client route was aligned with the backend `SETTLEMENT` document type.
- Remaining 🟡/🔴 items are primarily explicit design/acceptance constraints: real Windows/LAN/Tauri/hardware/Google Drive credential verification, DB-trigger-level audit immutability, universal optimistic-version protection, complete failure-matrix execution, compatibility/quality management UX, any locked rules still marked partial above; target historical snapshots are now persisted at Day End and payment retry idempotency is enforced for repair/refund/credit settlement events.


## V43 follow-up audit — 2026-09-26
- Shift End and Day End now have server-side verified-backup enforcement enabled by default.
- Sale-time product warranty records now retain duration/custom-rule configuration, including CUSTOM rule snapshots.
- POS customer history is now an inline history view covering sales, settlements and repairs.
- Migration `0019` is offline-SQL safe while retaining online duplicate detection; migration `0020_warranty_rule_snapshot` adds the warranty snapshot columns, and `0022_payment_idempotency` protects repair/refund/credit settlement retries.
- Verification: 56 backend tests passed, Python compile passed, Alembic head is `0022_payment_idempotency`, and offline migration SQL generation passed.


### V48 production hardening
- Windows server startup now waits for PostgreSQL readiness before migrations/server launch.
- Windows startup task and server preflight scripts are included.
- Deployment contract tests verify the startup/recovery configuration.
- These scripts improve deployment readiness but do not substitute for physical Windows/LAN acceptance on the shop laptops.


## Batch 2026-10-02 — Backend/contract hardening
- 🟢 Completed purchase history now exposes stable purchase-line IDs and item/supplier details to the Admin-only correction workflow.
- 🟢 Admin purchase creation accepts optional `supplier_id`; supplier assignment is validated server-side and an audited Admin correction endpoint is available.
- 🟢 Item Master now supports Admin-managed default warranty records for `NONE`, `DAYS`, `MONTHS`, `CHECKING ONLY`, and controlled `CUSTOM` rules. Sale-time warranty snapshot logic remains unchanged.
- 🟢 Customer history now includes product warranty claims linked through the sale-time warranty/sale-line/customer lineage.
- 🟢 Reload is now constrained server-side to one entry per business day/session, with provider allow-list validation and a PostgreSQL trigger for concurrency-safe enforcement. Existing historical duplicate rows are not deleted by the migration.
- 🟡 Backup emergency-target configuration remains deployment/configuration-level in this batch; physical target failure testing is still unverified.
- 🟡 Frontend Vite build remains unverified because the uploaded project has no installed `node_modules` in this environment.
- 🟢 Backend compile check passed; Alembic offline SQL generation passed; backend test suite passed at 77 tests.
