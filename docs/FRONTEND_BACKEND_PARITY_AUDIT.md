# Lovely Tech POS Frontend/Backend Parity Audit

**Audit date:** 2026-10-09  
**Scope:** Read-only source, documentation, and safe local checks in `C:\Lovely Tech POS`. No application files, configuration, migrations, database contents, accounts, shop records, or production settings were changed. No Git command was used.

**Bootstrap guard follow-up (2026-10-10):** Isolated changes now require the supported Alembic head (`0031_alembic_version_id_capacity`), all mapped tables and columns, and migration-managed `document_counters` before identity loading. Authorization assignments and document-counter rows count as existing state. PostgreSQL bootstrap explicitly sets and verifies `READ COMMITTED`, then takes a transaction-scoped advisory lock held through bootstrap writes. SQLite `BEGIN IMMEDIATE` is allowed only when `APP_ENV` is explicitly `test` or `development` and `SQLITE_BOOTSTRAP_FALLBACK_ENABLED=true`; both settings default to deny SQLite bootstrap (empty environment and false opt-in). Synthetic SQLite regressions cover schema rejection, opted-in first-time setup, and identity-write failure followed by a retry. Confirmed behavior: bootstrap commits the branch/Admin/session/audit rows before writing the external branch binding; a binding-write failure returns 500, and retry detects existing rows and rejects with 409 without creating a second branch/Admin or changing the identity file. This is fail-closed, not identity recovery; no automatic rebinding policy is implemented. No isolated PostgreSQL runtime was available, so PostgreSQL locking/schema behavior is **not runtime-verified**. Split-brain/old-writer fencing remains unimplemented; original findings below record the 2026-10-09 audit state.

## A. Executive Summary

**Overall status: FAIL for requirements parity; NOT VERIFIED for real-shop readiness.** The repository contains a substantial POS backend and frontend, but the production bundle has confirmed route mismatches that prevent the Day/Finance and Repair UI from reaching their registered backend routes. Static inspection also found backend response fields that disclose FIFO cost/profit to users with general report/repair/stock permissions, purchase payment-method loss that distorts cash reporting, incomplete idempotency, an unimplemented existing-shop form, no historical-import workflow, and unsafe/unverified replacement-server identity recovery. The current evidence does not support real-shop acceptance.

**Coverage counts:** 124 normative requirement rows checked (117 Markdown bullets plus seven separately numbered recovery scenarios); 150 active frontend interaction IDs inventoried; 89 frontend request/call-shape families inventoried from the production-bundle source map; 120 backend route decorators inventoried. The PDF comparison is a separate blocked evidence item and is not included in the 124 Markdown requirement count.

**Requirement status totals:** PASS 6; PARTIAL 65; FAIL 32; NOT IMPLEMENTED 7; NOT VERIFIED 14; BLOCKED 0. Totals sum to 124. PASS is limited to source-verifiable technical/control properties; it does not assert deployment or shop acceptance.

**What is verified:** A Vite production-mode bundle was built to an OS temporary directory; its source map showed 49 modules and selected adjacent `.js` files for most feature modules. A no-emit TypeScript check passed. The backend session configuration test passed, while a focused frontend-contract pytest selection had one failure. Source inspection verified the concrete path, role, and field mismatches cited below.

**What is only implemented or documented:** FIFO, sales, purchase corrections, returns, repairs, warranty, reports, backups, and provisioning have services/routes/models and related tests. The audit did not run their database-backed tests or perform any browser, physical printer, LAN, financial, import, installer, backup, or restore acceptance scenario. Existing status documents and tests are evidence of code/test presence, not new execution results.

**PDF/source reconciliation:** `docs/README.md` states `docs/REQUIREMENTS.md` is the maintained normative source and describes the historical-name PDF as reconciled. That precedence is followed. The PDF was located but not readable with available safe local tools: no `pdftotext`, `mutool`, or `qpdf` command and no `pypdf`, `PyPDF2`, `fitz`, or `pdfminer` module were available. No PDF contents are inferred. PDF comparison is **NOT VERIFIED**; no Markdown requirement is marked verified against the PDF.

**Material source/document discrepancy:** Normative [REQUIREMENTS.md](REQUIREMENTS.md) requires 30-minute idle expiry for both roles and a 10-minute critical reauthentication window. Current [`config.py`](../backend/app/core/config.py#L8-L16) sets Admin to 5 minutes, Cashier to 60 minutes, and absolute lifetimes to 12 hours; [`reauth.py`](../backend/app/security/reauth.py#L7-L14) verifies a password per protected action and stores no 10-minute reauthentication timestamp. `PROJECT_STATUS.md` records the same 5/60-minute values, so its implementation note is not an alternate requirement; it documents a known normative mismatch.

### Highest-risk findings

1. **Critical, identity recovery/rebinding and split-brain remain unresolved:** The fail-open bootstrap behavior described in the 2026-10-09 audit snapshot was subsequently corrected by database-state checks before identity loading. A separate failure window remains: [`provisioning.py`](../backend/app/api/routes/provisioning.py#L368-L380) commits bootstrap rows before saving the external branch binding. Isolated regression coverage confirms that a binding-write failure returns 500 and a retry fails closed with 409 without duplicates or identity overwrite. It does not provide a safe recovery/rebinding procedure; recovery must validate/reconcile Shop and Server Identity and establish one authorized writer before writes resume. The original finding below is retained as historical evidence, not current guard behavior.
2. **High, cashier cost/profit disclosure:** [`reports.py`](../backend/app/api/routes/reports.py#L47-L68) returns gross/net profit from `/reports/comparison`, unit costs from `/reports/stock-age`, and purchase unit costs from `/reports/purchases` under `REPORT_VIEW`/`STOCK_VIEW` without Admin response masking. [`repairs.py`](../backend/app/services/repairs.py#L101-L115) includes `fifo_cost` in repair detail, and the active UI displays it to all repair viewers in [`RepairWorkspace.js`](../frontend/src/features/repairs/RepairWorkspace.js#L190-L205). Hiding report selectors is not server authorization.
3. **High, core route mismatch:** the frontend calls `/api/v1/operations/...` for day status/start/end and repair list/detail/mutations. `operations.router` has no prefix and is included directly by [`router.py`](../backend/app/api/router.py#L3-L19), so registered paths are `/api/v1/day/...`, `/api/v1/repairs...`, `/api/v1/approvals...`, and `/api/v1/settlements...`. The dashboard's `Promise.all` also fails when `/operations/day/status` returns 404, preventing the combined status load. These are source-proven contract mismatches; no live HTTP request was made.
4. **High, incorrect cash classification:** the purchase schema accepts `payment_method`, but [`routes/purchases.py`](../backend/app/api/routes/purchases.py#L15-L28) omits it in the service call. [`services/purchases.py`](../backend/app/services/purchases.py#L25-L35) defaults it to CASH. [`services/reports.py`](../backend/app/services/reports.py#L102-L115) then subtracts only purchases and expenses marked CASH from Cash In Hands, even though the requirement includes all payment methods. Card/Online purchases are persisted as cash and later cash calculations are wrong.
5. **High, financial retries can duplicate records:** sale, purchase, repair-payment, refund-payment, and settlement client flows have some keys, but return creation, expense/other-income submission, repair creation, and cash-in do not pass stable idempotency keys. Their server schemas/services also permit missing keys for several paths. A timeout followed by a retry can create duplicate financial/business entries.
6. **High, mandatory import absent:** searches of the active frontend, backend application, and Windows scripts found no spreadsheet staging/import workflow. This is a normative pre-release gate, not merely an untested screen.

The original missing-identity regression and fail-closed guard have since been implemented and covered with isolated SQLite tests. A synthetic identity-write failure confirms that a retry cannot silently bootstrap a second shop, but identity recovery/rebinding remains an explicit unresolved decision. The smallest next bootstrap-safety task is to run the schema contract and two-connection lock tests against an explicitly isolated PostgreSQL instance; until that environment is available, production locking behavior remains unverified. Split-brain/old-writer fencing must remain separate, explicit follow-up work.

## B. Screen and Interaction Matrix

**Active-source rule:** [`index.html`](../frontend/index.html#L1) explicitly loads `main.tsx`. A safe Vite bundle was generated to `%TEMP%`; its source map resolves extensionless imports to adjacent `.js` files for `api/client`, `POSHome`, `DashboardLayout`, login, purchases, repairs, returns, warranty, settings, discovery, and machine config. TSX siblings are not assumed to be the bundled implementation. `SetupRequired`, `ServerBootstrapForm`, and `ServerExistingShopForm` are TSX-only and are included. The bundled `POSHome.js` contains an unrendered legacy `PurchasesTab`; it is not counted as a visible interaction. UI tests that import TSX may therefore test code different from the production bundle.

Status in this matrix means source-supported behavior, not browser acceptance. `PARTIAL` means wiring exists but end-to-end behavior, API compatibility, or relevant acceptance evidence is incomplete. `NOT IMPLEMENTED` means the action is decorative/no-op. `NOT VERIFIED` means source alone cannot establish behavior.

| ID | Screen / control | Expected behavior and actual outcome | Backend, permission, persistence, tests | Status |
|---|---|---|---|---|
| UI-001 | Startup discovery | Discover and verify server before POS; client boot calls shared resolver, mDNS command, then `/discovery/info`. | `discovery.ts`; public discovery endpoint. Mocked frontend boot tests inspected, not run. | PARTIAL |
| UI-002 | Retry discovery | Retry resolution and update setup state; handler resets resolver and retries. | Shared client; source in `main.tsx`. Mocked tests inspected. | PARTIAL |
| UI-003 | Configure manually entry point | Admin-only fallback; discovery error screen exposes it before authentication, with no role check. | `AdminManualServerPanel.js`; identity verifier but UI access is not Admin-gated during boot. | PARTIAL |
| UI-004 | Manual server Connect / Back / Cancel form | Validate host/URL and verify product/identity/setup state; shared client persists verified override. `server_reference` continuity is not enforced. | `verifyManualServer`; `GET /discovery/info`; no persistence to backend. | PARTIAL |
| UI-005 | Provision new shop card | Open first-admin bootstrap form. | `SetupRequired.tsx`; no DB action until submit. | PARTIAL |
| UI-006 | Bootstrap form | Validate branch/admin fields, POST `/provisioning/bootstrap`, persist session, refresh identity. | `provisioning.py`; unauthenticated first-run guard; DB transaction plus identity-file write. | PARTIAL |
| UI-007 | Complete existing shop card | Open existing-shop form. | `SetupRequired.tsx`; no mutation on open. | PARTIAL |
| UI-008 | Existing-shop form submit | Expected to bind/provision existing shop; handler only logs values and does not call API. | `ServerExistingShopForm.tsx#L10-L24`; no route, no persistence. | NOT IMPLEMENTED |
| UI-009 | Login form | Submit username/password; stores token/user on successful `/auth/login`; errors shown inline. | `Login.js`; `auth.py`; 401/lockout server behavior. Mocked/contract coverage only. | PARTIAL |
| UI-010 | Session expired transition | API client clears token/user on 401 and dispatches event; app returns to login. | `client.js#L122-L131`, `main.tsx`; server `current_user`. | PARTIAL |
| UI-011 | Error-boundary clear/reload | Clear session and reload; stack/message is rendered, so deployment logs/errors must be checked for sensitive data. | `main.tsx#L20-L39`; local-only storage mutation. | PARTIAL |
| UI-012 | Brand button | Navigate to Dashboard. | `DashboardLayout.js`; local tab state, no API. | PARTIAL |
| UI-013 | Dashboard navigation | Open Dashboard. | Local tab state in `POSHome.js`; no route URL. | PARTIAL |
| UI-014 | Sales navigation | Open POS screen. | Local tab state. | PARTIAL |
| UI-015 | Items navigation | Open item master. | Local tab state. | PARTIAL |
| UI-016 | Customers navigation | Open customer directory. | Local tab state. | PARTIAL |
| UI-017 | Repairs navigation | Open intake and repair workspace. | Local tab state; underlying calls have wrong `/operations` prefix. | FAIL |
| UI-018 | Warranty navigation | Open warranty workspace. | Local tab state; individual warranty calls mostly have matching route paths. | PARTIAL |
| UI-019 | Stock navigation | Open stock view. | Local tab state. | PARTIAL |
| UI-020 | Purchases navigation | Open imported `Purchases.js` component, not dead inline legacy component. | Local tab state; matching `/purchases` family. | PARTIAL |
| UI-021 | Cash/Day navigation | Open day finance panel. | Calls `/operations/day/...`; backend registers `/day/...`. | FAIL |
| UI-022 | Reports navigation | Open reports. | Report calls largely match routes; export bypasses shared client. | PARTIAL |
| UI-023 | Returns navigation | Open returns/exchange. | Calls matching sales/returns paths. | PARTIAL |
| UI-024 | Expenses navigation | Open expense/other-income form. | Admin expense-category fetch and create calls; other-income approval UI absent. | PARTIAL |
| UI-025 | Documents navigation | Open document search/reprint. | Calls matching document routes; endpoint records event only, does not print. | PARTIAL |
| UI-026 | Settings navigation | Open local preferences. | Local state/localStorage. | PARTIAL |
| UI-027 | Admin navigation | Admin-only tab. | UI role check; Admin endpoints still require server permission. | PARTIAL |
| UI-028 | Backup navigation | Admin-only tab. | UI role check plus `BACKUP_MANAGE`. | PARTIAL |
| UI-029 | Global quick-search field / Ctrl+K | Looks like product/customer/invoice search; keyboard handler only focuses/selects the input, no search request. | `DashboardLayout.js`; no backend call. | NOT IMPLEMENTED |
| UI-030 | Notifications icon | Clickable-looking control has no handler/action. | `DashboardLayout.js`; no persistence/API. | NOT IMPLEMENTED |
| UI-031 | Account avatar / logout | Calls server logout, then clears local session; server revokes all user sessions. | `client.js`, `auth.py`; not a local-only logout. | PARTIAL |
| UI-032 | Dashboard Refresh | Reload sales, day, backup, targets together; Promise rejection from bad day path fails the combined load. | `/reports/sales-summary`, `/operations/day/status`, `/backup/status`, `/reports/target-progress`; dashboard error banner. | FAIL |
| UI-033 | Dashboard New Sale | Navigate to Sales tab. | Local navigation. | PARTIAL |
| UI-034 | Dashboard Add Item | Navigate to Items tab. | Local navigation. | PARTIAL |
| UI-035 | Dashboard New Repair | Navigate to Repairs tab; repair screen then calls mismatched `/operations/...`. | Local navigation plus broken API contract. | FAIL |
| UI-036 | Dashboard Purchase | Navigate to Purchases tab. | Local navigation. | PARTIAL |
| UI-037 | Customer search / Find | GET customer list by name/contact; Enter and both Search/Find activate same call. | `GET /customers`; `SALE_CREATE`; list limit 50. | PARTIAL |
| UI-038 | Select customer row | Populate profile form; no persistence until save. | Local component state. | PARTIAL |
| UI-039 | Create customer form | POST optional name/contact/notes; button requires at least name or contact. | `POST /customers`, `SALE_CREATE`; audited DB commit. | PARTIAL |
| UI-040 | Save customer | PUT profile with version; stale version rejected; success alert and local row update. | `PUT /customers/{id}`, `SALE_CREATE`; version lock/audit. | PARTIAL |
| UI-041 | Customer History | Load sales, repairs, claims, settlements. | `GET /customers/{id}/history`, `REPORT_VIEW`; branch-filtered transactions, global customer row. | PARTIAL |
| UI-042 | Close history panel | Clear local history only. | Local state. | PARTIAL |
| UI-043 | Sale item search | Search item code/barcode/description. | `GET /inventory/items/search`, `STOCK_VIEW`; response excludes cost. | PARTIAL |
| UI-044 | Add item card to sale | Add/increment cart line. | Local cart until checkout; no persistence. | PARTIAL |
| UI-045 | Clear cart | Clear cart/discount approval local state. | No backend mutation. | PARTIAL |
| UI-046 | Find serialized unit | Query serial/IMEI results. | `GET /inventory/serialized/search`, `STOCK_VIEW`. | PARTIAL |
| UI-047 | Attach serialized unit | Attach selected available unit to matching cart item. | Local cart; backend validates unit/item/status on sale. | PARTIAL |
| UI-048 | Cart quantity/price/discount fields | Edit each line locally; checkout checks price and discount <= line gross; backend validates again. | `POST /sales`; Decimal schema/service. | PARTIAL |
| UI-049 | Sale warranty override selector | Set sale-time rule in payload; duration/custom validity is finally checked server-side. | `POST /sales`; sale snapshot service. | PARTIAL |
| UI-050 | Document type/manual invoice reference fields | Choose thermal/manual/no-print; manual ref required by UI for manual mode. No print call follows checkout. | Sale payload to `/sales`; invoice/document snapshot persisted. | PARTIAL |
| UI-051 | Sale customer search/select | Search and select customer for credit sale. | `GET /customers`; `SALE_CREATE`. | PARTIAL |
| UI-052 | Quick create customer | DOM-value-based name/contact create; result selected locally. | `POST /customers`; `SALE_CREATE`; audited commit. | PARTIAL |
| UI-053 | Sale customer history open/close | Load selected customer's history and close local panel. | `GET /customers/{id}/history`; `REPORT_VIEW`. | PARTIAL |
| UI-054 | Credit toggle / settlement inputs | Toggle credit, customer, amount and method controls; credit sale UI is not independently authoritative. | `/sales` rejects non-Admin credit sales; settlement path has `/operations` mismatch. | PARTIAL |
| UI-055 | Settle Credit | POST settlement with UUID key, show proof, then record reprint event. Route path is wrong (`/operations/settlements`). | Actual backend `/settlements`; `CREDIT_SETTLE`; service idempotency. | FAIL |
| UI-056 | Split payment inputs | Cash/Card/Online and cash received are entered; local equality check before sale. | `POST /sales`; schema/service total checks. | PARTIAL |
| UI-057 | Complete Sale | Guard empty/invalid cart, build sale snapshot and UUID idempotency key; reset key only after success; no physical print invoked. | `/sales` matches; `SALE_CREATE`, Admin credit gate, atomic DB service, sale response. | PARTIAL |
| UI-058 | Return Find Sale | Search completed sale by ID/invoice. | `GET /sales/{id}` matches `RETURN_CREATE`; branch-scoped response. | PARTIAL |
| UI-059 | Return Reset | Clear selected sale/lines/result locally. | No backend mutation. | PARTIAL |
| UI-060 | Return quantities/condition | Choose partial quantity and GOOD/DAMAGED per line; client caps to sold qty, backend rechecks. | Return request schema/service. | PARTIAL |
| UI-061 | Return charge/reason | Edit charge/reason; HTML minimum plus backend validation. | `POST /returns`; reason is not schema-required but service may validate. | PARTIAL |
| UI-062 | Complete Return | POST return without idempotency key/version; Admin role sends `admin_override=true`. | `POST /returns`; branch/7-day/lineage checks, one DB transaction. Retry duplicate risk. | PARTIAL |
| UI-063 | Load Return | Load return detail and refund payment list. | `GET /returns/{id}` and `/refund-payments`, `RETURN_CREATE`. | PARTIAL |
| UI-064 | Refund method/amount/reference form | Client rejects non-positive or above remaining amount; backend repeats remaining/payment validation. | `POST /returns/{id}/refund-payment`; request key generated. | PARTIAL |
| UI-065 | Record refund | Persist payment and reload return; key rotates after success. | Refund service idempotency/DB commit. | PARTIAL |
| UI-066 | Replacement sale ID field | Operator must create separate replacement sale and manually enter its sale ID. | Local field; no sale-picker/list endpoint. | PARTIAL |
| UI-067 | Complete exchange | POST separate completed return + replacement sale link; no idempotency key/version supplied. | `POST /returns/exchange`; exchange uniqueness and DB transaction. | PARTIAL |
| UI-068 | Repair intake fields/Create/Advance | Create repair, then optional payment with key; IMEI is embedded in Special Note because schema lacks a field. Create request itself has no idempotency. Both URLs use wrong `/operations` prefix. | Actual `/repairs`, `/repairs/{id}/payment`; `REPAIR_CREATE/PAYMENT`; service transaction. | FAIL |
| UI-069 | Clear repair intake | Reset form and local result. | No backend mutation. | PARTIAL |
| UI-070 | Repair list Refresh | GET repairs; wrong prefix means no matching route. | Actual `GET /repairs`; `REPAIR_CREATE`. | FAIL |
| UI-071 | Repair search/status filter | Filter client-loaded list; status choices omit WAITING FOR CUSTOMER and RETURNED TO CUSTOMER. | Local filtering; service supports full statuses. | PARTIAL |
| UI-072 | Select repair | Fetch repair detail; wrong prefix. | Actual `GET /repairs/{id}`. | FAIL |
| UI-073 | Repair detail Reload | Refresh detail/list; wrong prefix. | Same route mismatch. | FAIL |
| UI-074 | Repair status actions | UI flow only offers subset; POST wrong prefix; service persists status history/version checks. | Actual `/repairs/{id}/status`, `REPAIR_UPDATE`. | FAIL |
| UI-075 | Deliver / Hand Over | POST with version query; wrong prefix. | Actual `/repairs/{id}/deliver`; service Admin outstanding-balance override. | FAIL |
| UI-076 | Cancel repair | Prompt reason and POST version; wrong prefix. | Actual `/repairs/{id}/cancel`; service reverses used GOOD stock and preserves payment rows. | FAIL |
| UI-077 | Repair part search | Search item inventory. | `GET /inventory/items/search`, `STOCK_VIEW`. | PARTIAL |
| UI-078 | Use Part | Add FIFO part, quantity, charge, note; wrong prefix; service consumes FIFO. | Actual `/repairs/{id}/part`, `REPAIR_UPDATE`; transaction commit. | FAIL |
| UI-079 | Return Good part | Fixed reason; wrong prefix. | Actual `/repairs/{id}/part/{part_id}/remove`; restores original lot lineage. | FAIL |
| UI-080 | Mark damaged / review | Damaged part uses fixed reason; Admin review controls exist but path wrong and error surfaces via onError. | Actual `/repairs/{id}/part/{part_id}/damage-review`, `WARRANTY_DECIDE`. | FAIL |
| UI-081 | Final amount/labour/reference/finalize form | Checks final amount locally; version/finalize request uses wrong prefix. | Actual `/repairs/{id}/finalize`; service audited versioned update. | FAIL |
| UI-082 | Repair payment form | Cash/Card/Online, amount/reference, idempotency key; wrong prefix. | Actual `/repairs/{id}/payment`, `REPAIR_PAYMENT`; payment proof persisted. | FAIL |
| UI-083 | Repair proof Reprint | POST reprint event; wrong prefix only affects preceding detail retrieval, document endpoint itself matches. Does not physically print. | `/documents/REPAIR_PAYMENT/{id}/reprint`, `DOCUMENT_REPRINT`. | PARTIAL |
| UI-084 | Check repair warranty | Fetch repair warranty; wrong prefix. | Actual `/repairs/{id}/warranty`. | FAIL |
| UI-085 | Warranty serial lookup | Query serial/IMEI, show stored dates/status. | `/warranty/serial-lookup` exists; `WARRANTY_CREATE`. | PARTIAL |
| UI-086 | Warranty number lookup | Query warranty number and display. | `/warranty/lookup`, `WARRANTY_CREATE`. | PARTIAL |
| UI-087 | Warranty calculator | Select start/type/duration/custom rule and calculate. | `/warranty/calculator`, `WARRANTY_CREATE`; backend calendar calculation. | PARTIAL |
| UI-088 | Claim item search/select | Search inventory, choose item and claim quantity/warranty ID/notes. | Inventory search plus local form; `WARRANTY_CREATE`. | PARTIAL |
| UI-089 | Create warranty claim | POST claim, clear fields, reload. | `/warranty/claims`; `WARRANTY_CREATE`; transaction/audit service. | PARTIAL |
| UI-090 | Refresh claim list | Reload last 100 claims. | `GET /warranty/claims`; `WARRANTY_CREATE`. | PARTIAL |
| UI-091 | Admin claim decisions | Supplier/damage/replacement actions are Admin-gated in UI and backend; fixed notes/outcome fields limit detail. | Matching `POST /warranty/claims/{id}/{supplier|damage|replacement}`; versioned service. | PARTIAL |
| UI-092 | Manual warranty registration | Admin-only fields, validates reference/description, posts exception registration. | `/warranty/manual-registration`, `WARRANTY_DECIDE`; no actual bill-recovery lookup. | PARTIAL |
| UI-093 | Stock Refresh | Reload movement-derived stock; errors swallowed silently. | `GET /inventory/summary`, `STOCK_VIEW`. | PARTIAL |
| UI-094 | Serial/IMEI search | Search and display serial status; errors clear result without visible message. | `GET /inventory/serialized/search`, `STOCK_VIEW`. | PARTIAL |
| UI-095 | Filter stock | Local text filter only; no server query/pagination. | No additional API. | PARTIAL |
| UI-096 | Stock Age by Batch | Query current day range and display batch age/quantity, not cost. Backend response includes unit_cost. | `/reports/stock-age`, `STOCK_VIEW`; sensitive field leak remains in raw response. | FAIL |
| UI-097 | Purchase item search/select | Search items and add them to purchase draft. | Inventory search; `STOCK_VIEW`. | PARTIAL |
| UI-098 | Purchase date/reference/quantity/payment/supplier fields | Edit request fields; backend schema accepts payment_method but route drops it; selected lines use one shared quantity. | `PurchaseCreateIn`; route/service discrepancy. | FAIL |
| UI-099 | Remove selected purchase item | Remove locally from draft. | No persistence. | PARTIAL |
| UI-100 | Save Purchase | Sends UUID idempotency key; clears fields/reloads Admin data. | `/purchases`; `PURCHASE_ENTRY`; route omits payment_method. | PARTIAL |
| UI-101 | Pending cost refresh | Admin loads pending cost/supplier data. | `/purchases/pending-costs`, `/admin/suppliers`; `PURCHASE_COST`/Admin. | PARTIAL |
| UI-102 | Complete purchase cost | Admin enters cost, versions sent, reloads pending. | `/purchases/complete-cost`; purchase locks, creates FIFO lot/audit. | PARTIAL |
| UI-103 | Purchase history date range/load | Admin fetches full capped 500 rows then filters locally; only supported in imported component. | `/purchases/history`, `PURCHASE_COST`; no server date pagination. | PARTIAL |
| UI-104 | Cost/date/quantity/reference/supplier corrections | Dialogs/modal collect reason/password; versioned and audited; ref path uses dynamic POST. | Correct routes plus PUT supplier; `PURCHASE_COST` and reauth. | PARTIAL |
| UI-105 | Expense/Other Income mode toggle | Switch local form mode. | No mutation. | PARTIAL |
| UI-106 | Expense category refresh | Load categories; error shown in banner. | `GET /admin/expense-categories`; requires `EXPENSE_ENTRY`, Admin bypass. | PARTIAL |
| UI-107 | Expense/Other Income form submit | Create records; button busy-guarded but no idempotency key; no list/history refresh. | `/admin/expenses` or `/admin/other-income`; cashier rows pending, Admin rows approved. | PARTIAL |
| UI-108 | Day/Finance Refresh | Load day status and backup; wrong day prefix causes Promise failure. | Actual `/day/status`; `DAY_MANAGE`. | FAIL |
| UI-109 | Day Start form/denominations | Enforce denomination sum locally and submit; wrong prefix. | Actual `/day/start`; service validates denominations and commits. | FAIL |
| UI-110 | Shift End | Submit same-date range; wrong prefix; verified-backup guard on server. | Actual `/day/shift-end`; route mismatch. | FAIL |
| UI-111 | Continue Today | Admin-gated local button and server role gate; wrong prefix. | Actual `/day/continue`; Admin-only. | FAIL |
| UI-112 | Reload form | Provider/amount, one-per-day service constraint; wrong prefix. | Actual `/day/reload`; `DAY_MANAGE`. | FAIL |
| UI-113 | Cash In form | Amount/note; wrong prefix and no idempotency key. | Actual `/day/cash-in`; `DAY_MANAGE`; duplicate submission risk. | FAIL |
| UI-114 | Day End form | Requires denomination entry/reason and passes version; wrong prefix. | Actual `/day/{id}/end`; verified-backup requirement. | FAIL |
| UI-115 | Opening correction | Admin password/reason/version and denomination sum; wrong prefix. | Actual `/day/opening-correction`; `DAY_MANAGE` + reauth. | FAIL |
| UI-116 | Reopen day | Admin password; wrong prefix. | Actual `/day/reopen`; reauth/audit service. | FAIL |
| UI-117 | Report type/date fields | Select report and date range; Admin options disabled visually. | Several `/reports/*` calls; backend must remain authoritative. | PARTIAL |
| UI-118 | Today/yesterday/month/year/previous-month presets | Set date range locally; previous-month behavior is calendar-based UI. | No call until Load; comparison service uses equal-length previous period. | PARTIAL |
| UI-119 | Load report | Branch reports and comparison; catch to shared banner. | `/reports/*`; some APIs expose sensitive data to non-Admin roles. | PARTIAL |
| UI-120 | Excel/PDF export | Direct `fetch` uses `VITE_API_BASE`/`/api/v1`, not resolved discovery URL/shared timeout/error logic; download attempt. | `/reports/export/{type}/{fmt}` backend exists and checks Admin for protected report types. Tauri discovered-host routing mismatch. | FAIL |
| UI-121 | Document search | Search invoice/repair/payment proof. | `GET /documents/search`, `DOCUMENT_REPRINT`; list limited to 20 per type. | PARTIAL |
| UI-122 | Document Reprint | Records an event and displays event ID, but neither route nor frontend invokes a printer. | `POST /documents/{type}/{id}/reprint`; DB `DocumentEvent`. | FAIL |
| UI-123 | Item search | Filter admin list and load masters. | `/items/admin-list`, `/items/masters`; `ITEM_EDIT`. | PARTIAL |
| UI-124 | New/Edit item selection | Populate local form and variants. | `GET /items/{id}/variants`; source not role-hidden from all stock viewers. | PARTIAL |
| UI-125 | Save item form | Validate required description/category/type, POST/PUT item, separately PUT warranty default; partial failure can leave item saved but warranty update failed. | `ITEM_EDIT`; several DB commits, no encompassing transaction from UI. | PARTIAL |
| UI-126 | Add barcode | Add on create or append on edit. | `POST /items/{id}/barcodes`; duplicate conflict returned. | PARTIAL |
| UI-127 | Add variant | Submit name/value and append result locally. | `POST /items/{id}/variants`; backend validation/audit. | PARTIAL |
| UI-128 | Add category | Admin role/permission server check; alert after create. | `POST /items/categories`; Admin-only. | PARTIAL |
| UI-129 | Add item type / serialized checkbox | Create type; reset fields after success. | `POST /items/item-types`; Admin-only. | PARTIAL |
| UI-130 | Admin Refresh | Concurrently load role/user/target/approval/expense/audit/supplier/category data; one endpoint failure rejects all. | Multiple Admin/report endpoints; no granular partial loading. | PARTIAL |
| UI-131 | Add expense category | Validate nonempty and POST; reload. | `/admin/expense-categories`; Admin panel. | PARTIAL |
| UI-132 | Add supplier | Validate name and POST optional contact/address. | `/admin/suppliers`; Admin panel. | PARTIAL |
| UI-133 | Edit cashier discount limit | Validate 0..100 and version; save and reload. | `PUT /admin/users/{id}/discount-limit`; Admin permission/audit. | PARTIAL |
| UI-134 | Reset Cashier password | Requires admin/current and new password fields; success alert. | `/admin/users/reset-password`; Admin only; no forced-change UI was found. | PARTIAL |
| UI-135 | Expense approve/reject | Sends fixed reason and no version query; backend requires `version`, so request returns 409. | `POST /admin/expenses/{id}/decision`; Admin only and optimistic lock. | FAIL |
| UI-136 | Approval approve/reject | Sends no version, while route requires `payload.version`; request returns 409. Additionally UI path has wrong `/operations` prefix. | Actual `/approvals/{id}/review`; Admin permission/version lock. | FAIL |
| UI-137 | Add target | Posts type/value/period then refreshes; no client validation for positive/date order. | `/admin/targets`; `TARGET_MANAGE`, server validates. | PARTIAL |
| UI-138 | Stock adjustment | Search item, prompt password, send quantity/reason; no key in payload. | `/stock-control/adjust`; `STOCK_ADJUST` + reauth; idempotency schema exists but unused. | PARTIAL |
| UI-139 | Role permission checkboxes/save | Admin password prompt and PUT selected permissions; no explicit current version. | `/admin/roles/{id}/permissions`; Admin-only, validates codes/audits. | PARTIAL |
| UI-140 | Recent Audit list | Read-only last 20 from loaded audit rows. | `/admin/audit`; Admin only. | PARTIAL |
| UI-141 | Backup Refresh | List restore points. | `GET /backup/points`, `BACKUP_MANAGE`. | PARTIAL |
| UI-142 | Create backup | POST timestamped name, reload, success alert. | `/backup/create`; creates/encrypts/read-verifies local dump; actual pg_dump not run. | PARTIAL |
| UI-143 | Verify backup | POST verify and reload. | `/backup/verify/{id}`; local decrypt/integrity check; no test run here. | PARTIAL |
| UI-144 | Sync Google Drive | Manual POST sync; no automatic scheduler/retry UI. | `/backup/sync/{id}`; remote presence check only. | PARTIAL |
| UI-145 | Restore backup | Confirm prompt/password then POST restore; UI says completed on route response. | `/backup/restore/{id}`; Admin reauth, VERIFIED gate, safety backup; identity reconciliation/writer fencing absent. | PARTIAL |
| UI-146 | Settings manual server | Admin-only Settings entry opens manual panel; unlike startup fallback, this entry is behind UI role guard. | Verified discovery endpoint; localStorage only. | PARTIAL |
| UI-147 | Theme control | Light/dark/system writes localStorage and applies document theme. | Device-local only. | PARTIAL |
| UI-148 | Accent control | Swatch writes local preference and CSS variable. | Device-local only. | PARTIAL |
| UI-149 | Density control | Toggle compact/comfortable and persist locally. | Device-local only. | PARTIAL |
| UI-150 | Connection status / health polling | Poll `/health` every 15 seconds and update status; no auth header/timeout wrapper. | Direct shared-client health fetch; `GET /health`, not a readiness/database health check. | PARTIAL |

**Screen/state coverage notes:** The app uses local tabs, not URL routes. There are 14 always-visible business tabs plus Admin and Backup for Admin. Search/list endpoints have server-side limits (customers 50, item search up to 50, repairs/claims 100, documents 20/type, Admin item list 200, purchase history 500) but no general pagination or sorting controls. Loading/empty/error handling is inconsistent: `StockTab` swallows errors, many actions rely on one shared banner, and browser `alert`/`prompt` is used for confirmations/passwords. No Playwright/browser interaction was performed. Several visible controls have no search action (global quick search) or no handler (notifications). The app has no observed loading/success/error states proving the backend write persisted beyond its response and reload.

## C. Atomic Requirements Traceability Matrix

Each `REQ-x.yy` maps to the correspondingly numbered dash-list item in that numbered section of normative [REQUIREMENTS.md](REQUIREMENTS.md). The seven `REQ-14.SC-xx` rows are the separately numbered recovery scenarios in section 14. Tests listed are source-inspected unless explicitly listed as executed in section F.

| ID | Atomic requirement (short label) | Implementation evidence / related UI and tests | Status |
|---|---|---|---|
| REQ-1.01 | Required technology stack and REST/LAN | `backend/pyproject.toml`, `frontend/package.json`, `desktop/tauri/tauri.conf.json`; local Vite/TS check only. | PARTIAL |
| REQ-1.02 | DB access only through FastAPI | Frontend API client uses HTTP; SQLAlchemy is backend-only. | PASS |
| REQ-1.03 | UUID identities, atomic non-reused numbers | Models use UUID; `NumberingService`; no concurrent real-DB test run. | PARTIAL |
| REQ-1.04 | Decimal/fixed point money | `schemas/api.py`, SQLAlchemy `Numeric`; service calculations use Decimal. | PARTIAL |
| REQ-1.05 | Movement/lot FIFO and negative replay | `fifo/engine.py`, `fifo/replay.py`; relevant tests inspected, not run. | PARTIAL |
| REQ-1.06 | Backend authorization and response visibility | `deps.py`; report comparison, stock-age, purchases, repair detail leak costs/profit. | FAIL |
| REQ-1.07 | Append-only business/audit history | Migration 0030 selected triggers and service audit rows; not all histories/DB triggers exercised. | PARTIAL |
| REQ-1.08 | Idempotency, versioning, branch isolation | Several services support these; UI omits keys for return/expense/repair/cash-in and calls some routes incorrectly. | FAIL |
| REQ-1.09 | Printer independent of transaction | Adapters exist but sale/reprint workflows never call them. | FAIL |
| REQ-1.10 | Encrypted local + optional cloud backup | Fernet and local verification exist; durable retry/remote verification/fallback incomplete. | PARTIAL |
| REQ-1.11 | Pytest regression and Playwright acceptance | Configs/tests exist; no Playwright run; one selected pytest fails. | PARTIAL |
| REQ-1.12 | Cashier host/Admin client topology | Docs/scripts describe intent; no target-machine evidence. | NOT VERIFIED |
| REQ-1.13 | Same role-selectable installer; machine/user role independent | Local machine-role state exists; installer is separate server/client tooling. | FAIL |
| REQ-1.14 | Zero-IP automatic discovery and reconnect after router/IP change | mDNS and resolver code exist; reconnect/address-change not physically tested. | PARTIAL |
| REQ-1.15 | Trust only product/protocol/persistent identity | TXT/HTTP fields checked, but saved server reference and duplicate-shop identities not enforced. | PARTIAL |
| REQ-1.16 | Replacement recovery preserves Shop Identity | External instance file not backed up/reconciled; no safe rebind/fencing. | FAIL |
| REQ-1.17 | Routine operation independent of Git | Current runtime scripts do not invoke Git; target install acceptance not run. | NOT VERIFIED |
| REQ-2.01 | Cashier never sees costs/profit/backup detail | Backend returns unit_cost/FIFO/profit on multiple permissioned routes. | FAIL |
| REQ-2.02 | 30m idle, 12h absolute, 10m critical reauth | Code is 5m Admin/60m Cashier; 12h absolute; no timed reauth window. Executed session test asserts old values. | FAIL |
| REQ-2.03 | RBAC, branch isolation, recovery, revocation | Dependencies and recovery services exist; not every route/branch/revocation scenario tested. | PARTIAL |
| REQ-2.04 | Append-only security/financial events | Audit events exist for selected flows; other-income approval UI absent and restore completion only external journal. | PARTIAL |
| REQ-2.05 | Stable retry keys; reject conflicting payloads | Some services hash/replay keys; several frontend financial mutations omit keys. | FAIL |
| REQ-2.06 | Optimistic versions and locks | Routes/services commonly use `with_for_update` and versions; some UI calls omit required version (approval decisions). | PARTIAL |
| REQ-2.07 | No unsupported security/recovery claims | Maintained docs caution against acceptance claims; PDF unreadable and physical tests absent. | PASS |
| REQ-3.01 | Cash/Card/Online/split | Sale UI/schema/service support all; route path matches. No end-to-end sale executed. | PARTIAL |
| REQ-3.02 | Typed price, discount limit, Admin approval | UI and service implement limits/approval; request/approval routes present. | PARTIAL |
| REQ-3.03 | Admin-only credit sale | Route rejects non-Admin; UI role-dependent; no request test run here. | PARTIAL |
| REQ-3.04 | Atomic never-reused invoice number | Unique invoice field and numbering service; no concurrency DB test run. | PARTIAL |
| REQ-3.05 | Commit before print; printer failure cannot undo sale | Sale commits, but print is not invoked at all by active UI/route. | FAIL |
| REQ-3.06 | Reprint event audited separately | `DocumentEvent` reprint row committed; no printer action or physical acceptance. | PARTIAL |
| REQ-3.07 | Customer docs contain final price only | No actual generated receipt/invoice was exercised; no observed print integration. | NOT VERIFIED |
| REQ-3.08 | Duplicate clicks/timeouts do not duplicate sale/payment | Sale key present; refund/settlement/repair payment partial; missing keys on other flows. | PARTIAL |
| REQ-3.09 | Preserve sale-time business/warranty snapshots | Sale lines/warranty/payment/document schema/service persist snapshots; no end-to-end historical report test. | PARTIAL |
| REQ-4.01 | Movement/lot exact FIFO | Models/FIFO service present; tests inspected, not run in this task. | PARTIAL |
| REQ-4.02 | Warn/deterministically reconcile negative stock; preserve later lot | Negative-stock warning shown for sale; replay code exists, no concurrency/replay execution. | PARTIAL |
| REQ-4.03 | Deterministic negative allocation reconciliation | FIFO replay source exists; behavior not executed/DB-verified here. | NOT VERIFIED |
| REQ-4.04 | Audited purchase corrections and FIFO recalculation | Cost/date/quantity/reference routes and correction service exist; UI/backend route matching not integration-tested. | PARTIAL |
| REQ-4.05 | Preserve lineage; explicitly represent damage/loss | Return/repair source handles lineage and damage records; return damaged record auto-approved in service. | PARTIAL |
| REQ-5.01 | Seven-day/partial return and Admin override | Service checks seven-day window/role; UI sends Admin override; no explicit confirmation/retry key for return creation. | PARTIAL |
| REQ-5.02 | GOOD lineage restore; damaged to Damage/Loss | Service creates appropriate stock effects; no persisted integration test run. | PARTIAL |
| REQ-5.03 | Return charge/accounting; separate sale/exchange | Services model return and exchange separately; UI requires manually entered replacement sale ID and omits exchange version/key. | PARTIAL |
| REQ-5.04 | Private pending cost purchase | Separate pending-cost workflow and cost permissions exist; payment method is dropped by route. | PARTIAL |
| REQ-5.05 | Audited, versioned FIFO-safe purchase correction | Corrections lock/version/audit/replay in source; not integration-tested. | PARTIAL |
| REQ-6.01 | All required repair statuses/history | Service defines required statuses; active UI omits WAITING FOR CUSTOMER and RETURNED TO CUSTOMER controls. | PARTIAL |
| REQ-6.02 | Intake, labour-only, FIFO parts, good-lineage return | Service supports; frontend paths use unregistered `/operations` prefix. | FAIL |
| REQ-6.03 | Damaged parts to Admin review | Backend review endpoint/service exists; UI's `/operations` path does not match registered path. | FAIL |
| REQ-6.04 | Advances/final/split/balances/Admin delivery override | Service supports; active repair API paths mismatch; no business-flow test run. | FAIL |
| REQ-6.05 | Safe cancel, immutable payment history | Service reverses used good parts and retains payments; UI cancel route mismatches. | PARTIAL |
| REQ-6.06 | Repair references/estimates/customer/status/print/reprint | Persisted details exist; no physical printer call; all repair APIs in UI have prefix mismatch. | FAIL |
| REQ-7.01 | Sale-date warranty exact snapshot/override | Sale service creates product warranty; data snapshot; no live sale test run. | PARTIAL |
| REQ-7.02 | NONE/DAYS/MONTHS/CHECKING/CUSTOM | Calculator/service/schema support all five. | PARTIAL |
| REQ-7.03 | Separate claims; cashier create/Admin decide | Routes and UI gating exist; path matches; untested. | PARTIAL |
| REQ-7.04 | Supplier replacement is `WARRANTY_REPLACEMENT` | Service creates movement/outcome with required source type. | PARTIAL |
| REQ-7.05 | Rejections/manual exception/lost-bill recovery/reprints | Manual registration and some decision/reprint flows exist; lost-bill recovery path not found; warranty reprints not exposed. | PARTIAL |
| REQ-7.06 | Immutable sale-time warranty snapshot | Sale line warranty is stored; later-default immutability supported by schema/service; no test executed. | PARTIAL |
| REQ-8.01 | Required denominations | UI/service enumerate exactly 5000, 2000, 1000, 500, 100, 50, 20. | PASS |
| REQ-8.02 | Cash Drawer formula | Service calculates expected cash; UI calls wrong operation path; no DB reconciliation run. | FAIL |
| REQ-8.03 | Cash In Hands all inflows/outflows/all methods | Service counts all sales/repair/settlements but filters expenses/purchases to CASH only. | FAIL |
| REQ-8.04 | Expenses/purchases affect hands, not drawer | Day calculation excludes purchase/expense from drawer; Cash In Hands purchase payment method can be corrupted. | PARTIAL |
| REQ-8.05 | Shift End distinct from Day End | Separate service states exist; UI day routes are all mismatched. | PARTIAL |
| REQ-8.06 | One-hour continue/auto-close/reopen audited | Lazy close and reopen logic exist; UI paths mismatched; no clock-boundary DB test executed. | PARTIAL |
| REQ-8.07 | One/day brand-wise cash reload | One reload/day and provider set exist; UI route mismatch; no physical reconciliation. | PARTIAL |
| REQ-8.08 | Day-end denominations and difference reason | UI/service validations exist; route mismatch prevents active operation. | FAIL |
| REQ-9.01 | Pending approvals excluded until approved | Expense and other income APIs create pending entries; Admin UI handles expenses only, not other-income approval. | PARTIAL |
| REQ-9.02 | Admin approve/reject audit/categories | Expense approval and category flow; other-income decision route no UI. | PARTIAL |
| REQ-9.03 | Customer history and role-specific privacy | History includes sales/repairs/warranty/settlements; no role-specific field filtering or privacy acceptance was established. | PARTIAL |
| REQ-9.04 | Admin-only credit sales | Backend role check exists; see REQ-3.03. | PARTIAL |
| REQ-9.05 | Settlements as payment, proof/reprints | Settlement service proof/idempotency exists; UI route has wrong prefix; reprint is event-only. | FAIL |
| REQ-10.01 | Daily/monthly/yearly/custom reports for required categories | UI selects major categories/date presets and backend routes exist; some route outputs/permissions are unsafe and call flow untested. | PARTIAL |
| REQ-10.02 | Splits/comparison/PDF/Excel | Split fields and exports exist; direct export bypasses discovered API base; comparison period is same-span, not guaranteed previous calendar month. | PARTIAL |
| REQ-10.03 | Six target types | Type selector, target service, progress route include all listed types. | PARTIAL |
| REQ-10.04 | Cashier profit targets hidden; immutable snapshots | Target progress masks profit target fields and snapshots exist; other profit endpoints still leak. | PARTIAL |
| REQ-11.01 | Backup lifecycle states | Local created/verified and pending sync modeled; lifecycle does not demonstrate durable uploaded-remote verification. | PARTIAL |
| REQ-11.02 | Restore only VERIFIED | Restore route explicitly rejects missing/non-VERIFIED points. | PASS |
| REQ-11.03 | Reauth/safety backup/confirm/integrity/audit sequence | Reauth, confirm, selected VERIFIED, safety copy, restore journal exist; no post-restore identity reconciliation/audit transaction. | PARTIAL |
| REQ-11.04 | Retry cloud queue and avoid split brain | Manual sync endpoint only; no durable automatic retry/writer fencing. | FAIL |
| REQ-11.05 | Backup separate from DB working directory | Default backup root is `./backups`; target configuration/storage was not inspected. | NOT VERIFIED |
| REQ-11.06 | Verified backup required at close with fallback | Close gate checks a VERIFIED point; no alternate target/fallback selection workflow found. | FAIL |
| REQ-11.07 | Google Drive optional for ordinary LAN use | Local dump is independent, cloud upload catches error; internet-outage sale acceptance not run. | PARTIAL |
| REQ-11.08 | Recovery key custody/loss limitations | Operations doc explains secret dependency; actual custody/protection unverified. | NOT VERIFIED |
| REQ-12.01 | Import products/purchase/sales/customer history | No import workflow found in frontend/backend/scripts. | NOT IMPLEMENTED |
| REQ-12.02 | Staging/validation/mapping/duplicates/approval/write/reconcile | No import workflow found. | NOT IMPLEMENTED |
| REQ-12.03 | Preserve source history/provenance | No import workflow found. | NOT IMPLEMENTED |
| REQ-12.04 | Never fabricate unresolved history | No import workflow to enforce/report this. | NOT IMPLEMENTED |
| REQ-12.05 | Reconcile historical stock equation | No importer/reconciliation tooling found. | NOT IMPLEMENTED |
| REQ-12.06 | Approved import before acceptance | Mandatory gate cannot be met; no import approval evidence. | NOT IMPLEMENTED |
| REQ-13.01 | Clear safe validation/timeout/connectivity/recovery errors | Shared API timeout and setup errors exist, but some screen errors are swallowed and error boundary renders stack. | PARTIAL |
| REQ-13.02 | Authority/confirmation/audit/idempotency for consequential actions | Some flows comply; others omit keys/version/confirmation, e.g. returns/cash-in/expense, approvals. | PARTIAL |
| REQ-13.03 | Core LAN works without Internet | Architecture is local-server oriented; no outage acceptance executed. | NOT VERIFIED |
| REQ-13.04 | Tests/build/package/shop acceptance distinct | Docs/checklist explicitly separate gates; current checks show only local build/type/test subset. | PASS |
| REQ-14.01 | One installer guides server/client topology | Separate server installation and client packaging scripts; not a common guided role installer. | FAIL |
| REQ-14.02 | Machine role independent of user role | `machine-config.ts` stores machine role separately; server/client auto-detect/no role wizard and no machine acceptance. | PARTIAL |
| REQ-14.03 | Owner client may be off without server outage | Intended in docs; not tested on target machines. | NOT VERIFIED |
| REQ-14.04 | Setup/upgrades do not require technical config/manual migrations | Server scripts require env/database config; installer flow absent. | FAIL |
| REQ-14.05 | Stable logical Shop Identity | Source uses branch code/branch row; separate immutable shop identity not demonstrated. | FAIL |
| REQ-14.06 | Authorized persistent Server Identity, exactly one writer | `instance_id` file persists normally; no shop binding/exclusive writer mechanism. | FAIL |
| REQ-14.07 | Machine Identity local and distinct | Client local `client_id` and `server_reference` exist; no server enforcement/replace acceptance. | PARTIAL |
| REQ-14.08 | Restore reconcile identity before advertising writes | Restore checks DB connectivity only; no identity rebind/fencing. | FAIL |
| REQ-14.09 | Bind verified identity, not IP | Discovery resolves current address but overwrites `server_reference` without comparing old value. | PARTIAL |
| REQ-14.10 | Conflicts/split brain fail closed | Resolver accepts first verified candidate; no duplicate shop/writer fencing. | FAIL |
| REQ-14.11 | Automatic mDNS discovery/reconnect | mDNS plus runtime resolver exist; no reconnect/IP-change acceptance. | PARTIAL |
| REQ-14.12 | Verify product/protocol/setup/identity | Checks identity fields against HTTP discovery; no multi-candidate ambiguity check. | PARTIAL |
| REQ-14.13 | Reject incomplete/ambiguous; manual path same checks/Admin fallback | Manual identity validates fields but startup fallback is not role-gated and prior server identity is not pinned. | PARTIAL |
| REQ-14.14 | No fixed IP in discovery/manual fallback | Production script uses relative base/runtime mDNS; manual fallback allows address as documented. | PARTIAL |
| REQ-14.15 | Guided connect/new/restore choices | New-shop UI exists; existing-shop submit is no-op; restore wizard absent. | FAIL |
| REQ-14.16 | New shop creates first Admin/security/recovery material safely | Bootstrap creates Admin and persists session; recovery-material/key custody choices absent. | PARTIAL |
| REQ-14.17 | Admin-only recovery/rebind/restore with reauth/audit | Restore is permission/Admin-password gated; identity ownership/rebind absent; pre-restore DB event may be overwritten. | PARTIAL |
| REQ-14.18 | Wizard avoids technical setup; fail before writes | No complete wizard; existing-shop form no-op; operator scripts require config/migrations. | FAIL |
| REQ-14.19 | Local transactions survive cloud outage | DB-backed local design exists; no outage/integration acceptance executed. | NOT VERIFIED |
| REQ-14.20 | Distinguish persisted sale from backup transport | Code uses DB transaction and backup path separately; no outage acceptance/test proves user-visible distinction. | PARTIAL |
| REQ-14.21 | Encrypted local copy, durable retry, verified remote sync | Encryption/readback local, manual remote sync; no durable retry/remote integrity check. | FAIL |
| REQ-14.22 | Verified-only restore sequence plus identity/audit | Verified gate/safety backup/reauth/confirm exist; identity checks and post-restore immutable audit incomplete. | PARTIAL |
| REQ-14.23 | Do not promise beyond available backup/key | Operations docs state limits; actual target retention/key custody unverified. | PASS |
| REQ-14.24 | Supported signed/integrity-checked upgrade and protocol gate | No supported application upgrade/version compatibility workflow found. | NOT IMPLEMENTED |
| REQ-14.25 | Pre-upgrade backup, migration once, health/identity/audit | No supported upgrade workflow or staging execution evidence. | FAIL |
| REQ-14.26 | Staging upgrade/rollback test and no manual SQL | Staging script exists, but migration/rollback/recovery sequence is not supplied or run. | NOT VERIFIED |
| REQ-14.27 | Upgrade/recovery preserve one writer/shop identity | No writer fencing or identity-preserving recovery workflow. | FAIL |
| REQ-14.SC-01 | Router replacement/DHCP change reconnect | No physical LAN test. | NOT VERIFIED |
| REQ-14.SC-02 | Replacement server restore and identity reconcile | Current restore/bootstrap identity path is unsafe/incomplete. | FAIL |
| REQ-14.SC-03 | Replace client and keep shop history | Client ID/discovery code exists; not tested on replacement laptop. | NOT VERIFIED |
| REQ-14.SC-04 | Replace server and all clients | No end-to-end acceptance evidence or safe writer rebinding. | NOT VERIFIED |
| REQ-14.SC-05 | New empty shop is distinct from restore | Bootstrap path exists; initial server-role flow exists, but no guided installer acceptance. | PARTIAL |
| REQ-14.SC-06 | Owner/Admin laptop off while LAN POS continues | No physical acceptance. | NOT VERIFIED |
| REQ-14.SC-07 | No backup/failed restore/key/identity/split-brain fails closed | Verified-only guard exists, but missing identity can bootstrap against restored DB and split brain is not fenced. | FAIL |

**Requirements total:** 124 rows. Totals: PASS 6; PARTIAL 65; FAIL 32; NOT IMPLEMENTED 7; NOT VERIFIED 14; BLOCKED 0. PDF comparison is tracked separately as `PDF-CMP-01: NOT VERIFIED`.

## D. Frontend/Backend API Contract Matrix

**Counting method:** 89 unique frontend method/path call shapes were extracted from files confirmed in the successful production source map, deduplicating repeated calls to the same template and grouping dynamic helper calls as one call family. This includes direct `fetch` calls and shared `api()` calls; dynamic repair/purchase/warranty subpaths are expanded below. The separate backend catalog contains all 120 route decorators. `main.tsx` is the entry, but extensionless imports resolve to `.js` siblings in the built output. The report's `api()` request contracts are not proof of successful HTTP behavior.

| Contract family | Frontend method/path shape and caller | Backend route/method | Auth, payload/response, persistence and compatibility |
|---|---|---|---|
| C-001 | GET `/health` via `checkServerHealth`, `DashboardLayout.js` | `main.py` GET `/health` | No auth; JSON `status`; health only, not DB readiness. No timeout in helper. PARTIAL. |
| C-002 | GET `http://127.0.0.1:8000/discovery/info`, `main.tsx` | `discovery.py` GET `/discovery/info` | Local role probe checks product/instance only; not mDNS identity verification. PARTIAL. |
| C-003 | GET `/discovery/info` via resolver/manual host | `discovery.py` GET `/discovery/info` | Public; product/protocol/app/instance/branch/setup response; source matches discovery validator. PARTIAL. |
| C-004 | POST `/auth/login`, `client.js` | `auth.py` POST `/auth/login` | LoginIn/LoginOut compatible; token persisted in localStorage; DB session. PARTIAL. |
| C-005 | POST `/auth/logout`, `client.js` | `auth.py` POST `/auth/logout` | Bearer current user; revokes all active user sessions. PARTIAL. |
| C-006 | POST `/provisioning/bootstrap`, `client.js`/`ServerBootstrapForm.tsx` | `provisioning.py` POST `/provisioning/bootstrap` | BootstrapIn/Out; unauthenticated first-run guard; DB commits before external identity-file write. Existing DB guard fails open when identity has no branch_code. FAIL. |
| C-007 | GET `/customers?q=...`, directory and sale flows | `customers.py` GET `/customers` | `SALE_CREATE`; response list of customer id/name/contact/version; 50-row limit. PARTIAL. |
| C-008 | POST `/customers`, directory and sale quick-create | `customers.py` POST `/customers` | CustomerIn, audited DB create. PARTIAL. |
| C-009 | PUT `/customers/{id}`, customer profile | `customers.py` PUT | CustomerUpdateIn/version; audit and lock. PARTIAL. |
| C-010 | GET `/customers/{id}/history`, customer/sale | `customers.py` GET | `REPORT_VIEW`; branch-filtered business data, no route-level customer branch field. PARTIAL. |
| C-011 | GET `/inventory/items/search?q=...`, sale/purchase/repair/warranty/admin | `inventory.py` GET `/inventory/items/search` | `STOCK_VIEW`; bounded query and response without cost. PARTIAL. |
| C-012 | GET `/inventory/summary`, Stock | `inventory.py` GET `/inventory/summary` | `STOCK_VIEW`; movement-derived stock. PARTIAL. |
| C-013 | GET `/inventory/serialized/search?q=...`, sale/stock | `inventory.py` GET `/inventory/serialized/search` | `STOCK_VIEW`; branch-scoped serial result. PARTIAL. |
| C-014 | GET `/items/admin-list?q=...`, item master | `items.py` GET `/items/admin-list` | `ITEM_EDIT`; item/barcode/warranty-default data; cost excluded. PARTIAL. |
| C-015 | GET `/items/masters`, item master | `items.py` GET `/items/masters` | `ITEM_EDIT`; category/type lists. PARTIAL. |
| C-016 | POST `/items`, create item | `items.py` POST `/items` | ItemCreateIn; `ITEM_EDIT`; audited commit. PARTIAL. |
| C-017 | PUT `/items/{id}`, edit item | `items.py` PUT | ItemUpdateIn/version; lock/audit. PARTIAL. |
| C-018 | POST `/items/{id}/barcodes`, add barcode | `items.py` POST | BarcodeIn; unique conflict; commit/audit. PARTIAL. |
| C-019 | PUT `/items/{id}/warranty-default`, save item | `items.py` PUT | WarrantyDefaultIn, Admin-only. Separate commit from item save can leave partial update. PARTIAL. |
| C-020 | GET `/items/{id}/variants`, edit item | `items.py` GET | `STOCK_VIEW`; response variants. PARTIAL. |
| C-021 | POST `/items/{id}/variants`, add variant | `items.py` POST | `ITEM_EDIT`; validates name/value; audit. PARTIAL. |
| C-022 | POST `/items/categories`, Admin | `items.py` POST | `ITEM_EDIT` plus explicit Admin; untyped dict validation. PARTIAL. |
| C-023 | POST `/items/item-types`, Admin | `items.py` POST | `ITEM_EDIT` plus explicit Admin; untyped dict validation. PARTIAL. |
| C-024 | POST `/sales`, sale checkout | `sales.py` POST `/sales` | SaleIn/Out, `SALE_CREATE`, Admin credit, Decimal validation, service commit/idempotency/FIFO. Match at source; no sale executed. PARTIAL. |
| C-025 | POST `/sales/discount-approval`, discount over-limit path | `sales.py` POST | `APPROVAL_REQUEST`; stores approval payload, returns approval ID. PARTIAL. |
| C-026 | GET `/sales/{id}`, return lookup | `sales.py` GET | `RETURN_CREATE`; branch/completed sale and line snapshot. PARTIAL. |
| C-027 | POST `/returns`, return creation | `returns.py` POST `/returns` | ReturnIn; `RETURN_CREATE`; service commit/lineage/idempotency optional. UI omits idempotency key. PARTIAL. |
| C-028 | POST `/returns/exchange`, exchange | `returns.py` POST | ExchangeIn; separate completed return/sale, version optional, no UI key. PARTIAL. |
| C-029 | POST `/returns/{id}/refund-payment`, refund | `returns.py` POST | ReturnPaymentIn; key in UI; locked service/DB commit. PARTIAL. |
| C-030 | GET `/returns/{id}`, load return | `returns.py` GET | `RETURN_CREATE`; return lines/status/totals. PARTIAL. |
| C-031 | GET `/returns/{id}/refund-payments`, load refund history | `returns.py` GET | `RETURN_CREATE`; payment rows. PARTIAL. |
| C-032 | GET `/operations/repairs`, UI repair list | No route at this path. Actual route is GET `/api/v1/repairs`. | UI uses unregistered prefix; no compatible HTTP contract. FAIL. |
| C-033 | GET `/operations/repairs/{id}`, repair detail | No route at this path. Actual GET `/api/v1/repairs/{id}`. | Prefix mismatch; UI never reaches detail service. FAIL. |
| C-034 | GET `/operations/repairs/{id}/warranty`, repair warranty | No route at this path. Actual GET `/api/v1/repairs/{id}/warranty`. | Prefix mismatch. FAIL. |
| C-035 | POST `/operations/repairs`, repair create | No route at this path. Actual POST `/api/v1/repairs`. | Prefix mismatch; create service not reached. FAIL. |
| C-036 | POST `/operations/repairs/{id}/status` | No route at this path. Actual POST `/api/v1/repairs/{id}/status`. | Prefix mismatch. FAIL. |
| C-037 | POST `/operations/repairs/{id}/payment` | No route at this path. Actual POST `/api/v1/repairs/{id}/payment`. | Prefix mismatch; key doesn't help unreachable path. FAIL. |
| C-038 | POST `/operations/repairs/{id}/finalize` | No route at this path. Actual POST `/api/v1/repairs/{id}/finalize`. | Prefix mismatch. FAIL. |
| C-039 | POST `/operations/repairs/{id}/deliver` | No route at this path. Actual POST `/api/v1/repairs/{id}/deliver`. | Prefix mismatch. FAIL. |
| C-040 | POST `/operations/repairs/{id}/cancel` | No route at this path. Actual POST `/api/v1/repairs/{id}/cancel`. | Prefix mismatch. FAIL. |
| C-041 | POST `/operations/repairs/{id}/part` | No route at this path. Actual POST `/api/v1/repairs/{id}/part`. | Prefix mismatch. FAIL. |
| C-042 | POST `/operations/repairs/{id}/part/{part}/remove` | No route at this path. Actual POST `/api/v1/repairs/{id}/part/{part}/remove`. | Prefix mismatch. FAIL. |
| C-043 | POST `/operations/repairs/{id}/part/{part}/damage-review` | No route at this path. Actual POST `/api/v1/repairs/{id}/part/{part}/damage-review`. | Prefix mismatch. FAIL. |
| C-044 | POST `/operations/day/status` | No route at this path. Actual GET `/api/v1/day/status`. | Both prefix and method mismatch. Dashboard/day load fails. FAIL. |
| C-045 | POST `/operations/day/start` | No route at this path. Actual POST `/api/v1/day/start`. | Prefix mismatch. FAIL. |
| C-046 | POST `/operations/day/opening-correction` | No route at this path. Actual POST `/api/v1/day/opening-correction`. | Prefix mismatch. FAIL. |
| C-047 | POST `/operations/day/continue` | No route at this path. Actual POST `/api/v1/day/continue`. | Prefix mismatch. FAIL. |
| C-048 | POST `/operations/day/reload` | No route at this path. Actual POST `/api/v1/day/reload`. | Prefix mismatch. FAIL. |
| C-049 | POST `/operations/day/cash-in` | No route at this path. Actual POST `/api/v1/day/cash-in`. | Prefix mismatch. FAIL. |
| C-050 | POST `/operations/day/shift-end` | No route at this path. Actual POST `/api/v1/day/shift-end`. | Prefix mismatch. FAIL. |
| C-051 | POST `/operations/day/reopen` | No route at this path. Actual POST `/api/v1/day/reopen`. | Prefix mismatch. FAIL. |
| C-052 | POST `/operations/day/{id}/end` | No route at this path. Actual POST `/api/v1/day/{id}/end`. | Prefix mismatch. FAIL. |
| C-053 | POST `/operations/settlements`, credit settlement | No route at this path. Actual POST `/api/v1/settlements`. | Prefix mismatch. FAIL. |
| C-054 | POST `/operations/approvals/{id}/review`, Admin approval | No route at this path. Actual POST `/api/v1/approvals/{id}/review`. | Prefix mismatch; payload also omits required `version`. FAIL. |
| C-055 | GET `/backup/status`, dashboard/day | `backup.py` GET `/backup/status` | Authenticated user; latest verified backup summary. PARTIAL. |
| C-056 | GET `/backup/points`, backup panel | `backup.py` GET `/backup/points` | `BACKUP_MANAGE`; up to 100 points. PARTIAL. |
| C-057 | POST `/backup/create`, backup panel | `backup.py` POST `/backup/create` | `BACKUP_MANAGE`; pg_dump/encrypt/readback, DB point/audit; actual DB operation not run. PARTIAL. |
| C-058 | POST `/backup/verify/{id}`, backup panel | `backup.py` POST | `BACKUP_MANAGE`; decrypt/integrity verification and state commit. PARTIAL. |
| C-059 | POST `/backup/sync/{id}`, backup panel | `backup.py` POST | `BACKUP_MANAGE`; manual rclone copy, verifies remote listing/name only, no automatic retry. PARTIAL. |
| C-060 | POST `/backup/restore/{id}?confirm=true&admin_password=...` | `backup.py` POST | `BACKUP_MANAGE` + Admin password; verified point/safety copy/pg_restore/connectivity; no identity reconciliation. PARTIAL. |
| C-061 | GET `/warranty/claims`, warranty workspace | `warranty.py` GET | `WARRANTY_CREATE`; branch-scoped 100-row list. PARTIAL. |
| C-062 | GET `/warranty/calculator`, calculator | `warranty.py` GET | `WARRANTY_CREATE`; date/type params compatible. PARTIAL. |
| C-063 | GET `/warranty/serial-lookup`, serial field | `warranty.py` GET | `WARRANTY_CREATE`; `serial_number` query compatible. PARTIAL. |
| C-064 | GET `/warranty/lookup`, warranty number | `warranty.py` GET | `WARRANTY_CREATE`; query compatible. PARTIAL. |
| C-065 | POST `/warranty/claims`, claim create | `warranty.py` POST | `WARRANTY_CREATE`; WarrantyClaimIn compatible; service commit/audit. PARTIAL. |
| C-066 | POST `/warranty/claims/{id}/supplier` | `warranty.py` POST | `WARRANTY_DECIDE`; version/body compatible. PARTIAL. |
| C-067 | POST `/warranty/claims/{id}/damage` | `warranty.py` POST | `WARRANTY_DECIDE`; version/body compatible. PARTIAL. |
| C-068 | POST `/warranty/claims/{id}/replacement` | `warranty.py` POST | `WARRANTY_DECIDE`; version/quantity default and replacement movement. PARTIAL. |
| C-069 | POST `/warranty/manual-registration` | `warranty.py` POST | `WARRANTY_DECIDE`; field schema compatible; audited registration. PARTIAL. |
| C-070 | GET `/purchases/pending-costs`, Purchases | `purchases.py` GET | `PURCHASE_COST`; typed response includes versions and pending cost fields. PARTIAL. |
| C-071 | GET `/purchases/history`, Purchases | `purchases.py` GET | `PURCHASE_COST`; typed response includes unit_cost; route lacks date query, UI filters locally. PARTIAL. |
| C-072 | POST `/purchases`, create | `purchases.py` POST | `PURCHASE_ENTRY`; PurchaseCreateIn accepts payment_method but route omits it in service call; persisted default CASH. FAIL. |
| C-073 | POST `/purchases/complete-cost` | `purchases.py` POST | `PURCHASE_COST`; purchase/line versions required; FIFO lot and audit. PARTIAL. |
| C-074 | POST `/purchases/correct-cost` | `purchases.py` POST | `PURCHASE_COST` + Admin reauth; version and reason, FIFO replay. PARTIAL. |
| C-075 | POST `/purchases/correct-date` | `purchases.py` POST | Same auth/version/audit/correction service. PARTIAL. |
| C-076 | POST `/purchases/correct-quantity` | `purchases.py` POST | Same; correction service protects lot lineage. PARTIAL. |
| C-077 | POST `/purchases/correct-reference` | `purchases.py` POST | Same; version/reason/audit. PARTIAL. |
| C-078 | PUT `/purchases/{id}/supplier` | `purchases.py` PUT | `PURCHASE_COST` + reauth, version/query; audited. PARTIAL. |
| C-079 | GET `/admin/users`, users panel | `admin.py` GET | Admin panel dependency; returns discount/version info. PARTIAL. |
| C-080 | PUT `/admin/users/{id}/discount-limit` | `admin.py` PUT | Admin-only, version required, audited. PARTIAL. |
| C-081 | GET `/admin/roles`, role editor | `admin.py` GET | Admin-only. PARTIAL. |
| C-082 | PUT `/admin/roles/{id}/permissions` | `admin.py` PUT | Admin reauth and validated codes; audited. PARTIAL. |
| C-083 | GET `/admin/permissions`, role editor | `admin.py` GET | Admin-only. PARTIAL. |
| C-084 | GET `/admin/targets`, target panel | `admin.py` GET | `TARGET_MANAGE`; branch-filtered. PARTIAL. |
| C-085 | POST `/admin/targets`, target create | `admin.py` POST | `TARGET_MANAGE`; period check/commit. PARTIAL. |
| C-086 | GET `/admin/approvals`, Admin panel | `admin.py` GET | Admin-only; payload may include persisted request JSON. PARTIAL. |
| C-087 | GET `/admin/pending-expenses`, Admin panel | `admin.py` GET | Admin-only pending expenses. PARTIAL. |
| C-088 | POST `/admin/expenses/{id}/decision?approve&reason`, Admin UI | `admin.py` POST | Admin-only route requires version, but UI omits it: predictable 409. FAIL. |
| C-089 | GET `/admin/audit`, Admin panel | `admin.py` GET | Admin-only; recent audit rows. PARTIAL. |
| C-090 | GET `/admin/expense-categories`, expense form | `admin.py` GET | `EXPENSE_ENTRY`; compatible response. PARTIAL. |
| C-091 | POST `/admin/expenses`, expense submit | `admin.py` POST | `EXPENSE_ENTRY`; idempotency optional, UI omits key; transaction commits. PARTIAL. |
| C-092 | POST `/admin/other-income`, income submit | `admin.py` POST | `OTHER_INCOME_ENTRY`; idempotency optional, UI omits key. PARTIAL. |
| C-093 | POST `/admin/expense-categories`, Admin create | `admin.py` POST | Admin panel; untyped dict but name validated. PARTIAL. |
| C-094 | POST `/admin/suppliers`, Admin create | `admin.py` POST | Admin-only, untyped dict with name check. PARTIAL. |
| C-095 | GET `/admin/suppliers`, purchase/Admin | `admin.py` GET | Admin-only. PARTIAL. |
| C-096 | POST `/admin/users/reset-password` | `admin.py` POST | Admin-only plus service password verification; UI has no forced-password-change screen. PARTIAL. |
| C-097 | POST `/reports/sales-summary`, dashboard/report | `reports.py` POST | `REPORT_VIEW`; schema masks fields for non-Admin, but other report routes do not. PARTIAL. |
| C-098 | POST `/reports/target-progress`, dashboard | `reports.py` POST | `REPORT_VIEW`; hides profit target numerics for non-Admin. PARTIAL. |
| C-099 | POST `/reports/target-history`, Admin | `reports.py` POST | Explicit Admin-only; immutable snapshots. PARTIAL. |
| C-100 | POST `/reports/cashiers`, report | `reports.py` POST | `REPORT_VIEW` plus explicit Admin. PARTIAL. |
| C-101 | POST `/reports/cash-in-hands`, report | `reports.py` POST | `CASH_HANDS_VIEW`; all-method calculation requirement not met by service. FAIL. |
| C-102 | POST `/reports/comparison`, report | `reports.py` POST | `REPORT_VIEW`; returns gross_profit/net_profit without Admin mask. FAIL. |
| C-103 | POST `/reports/stock-age`, stock view | `reports.py` POST | `STOCK_VIEW`; returns `unit_cost` directly. FAIL. |
| C-104 | POST `/reports/purchases`, report | `reports.py` POST | `REPORT_VIEW`; returns `unit_cost` without Admin restriction. FAIL. |
| C-105 | POST `/reports/repairs`, report | `reports.py` POST | `REPORT_VIEW`; response includes charges/payments, no unit cost. PARTIAL. |
| C-106 | POST `/reports/warranty`, report | `reports.py` POST | `REPORT_VIEW`; typed by returned dict. PARTIAL. |
| C-107 | POST `/reports/cash-drawer`, report | `reports.py` POST | `DAY_MANAGE`; route returns reconciled DayEnd rows. PARTIAL. |
| C-108 | Direct `fetch` `/reports/export/{type}/{pdf|xlsx}`, report | `reports.py` POST | Backend authorization exists; Tauri client uses relative env base, not discovered server, so wrong origin in packaged LAN client. FAIL. |
| C-109 | GET `/documents/search?q=...` | `documents.py` GET | `DOCUMENT_REPRINT`; sale/repair/payment/settlement results. PARTIAL. |
| C-110 | POST `/documents/{type}/{id}/reprint` | `documents.py` POST | `DOCUMENT_REPRINT`; writes DocumentEvent only, no printer adapter invoked. FAIL. |
| C-111 | POST `/operations/day/*`, client helpers | No registered `/operations` prefix; actual operation routes listed C-044–053. | Route mismatch, not an alternate alias. FAIL. |
| C-112 | POST `/operations/repairs/*`, repair workspace | No registered `/operations` prefix; actual repair routes listed C-032–043. | Route mismatch, not an alternate alias. FAIL. |
| C-113 | POST `/stock-control/adjust?admin_password=...` | `stock_control.py` POST `/stock-control/adjust` | `STOCK_ADJUST` + Admin reauth; UI omits idempotency key accepted by schema. PARTIAL. |
| C-114 | GET `/auth/me` | `auth.py` GET `/auth/me`; no frontend caller. | Authenticated current-user response; no UI refresh/session revalidation flow. NOT IMPLEMENTED. |
| C-115 | POST `/auth/admin/recovery-code` | `auth.py` POST `/auth/admin/recovery-code`; no frontend caller. | Authenticated Admin-only; returns recovery code, service commit. NOT IMPLEMENTED. |
| C-116 | POST `/auth/admin/recover` | `auth.py` POST `/auth/admin/recover`; no frontend caller. | Unauthenticated recovery-code/password request, revokes sessions; no recovery form. NOT IMPLEMENTED. |
| C-117 | POST `/auth/change-password` | `auth.py` POST `/auth/change-password`; no frontend caller. | Bearer session/current-password validation; forced-change UI absent. NOT IMPLEMENTED. |
| C-118 | POST `/admin/other-income/{id}/decision` | Backend route only; no list/decision UI for other income. | `admin.py` Admin-only, version required; inaccessible workflow. NOT IMPLEMENTED. |
| C-119 | PUT `/admin/users/{id}/role` | Backend route only; role editing UI only changes permission sets, not user role. | Admin-only/versioned. NOT IMPLEMENTED. |
| C-120 | POST `/stock-control/damage-loss` | Backend route only; no direct stock damage/loss UI. | `STOCK_ADJUST`; damage review in repairs is a different flow. NOT IMPLEMENTED. |
| C-121 | GET `/permissions/mine` | `permissions.py` GET `/permissions/mine`; no frontend caller. | Bearer permission dependency; no UI fetch of current permission list. NOT IMPLEMENTED. |
| C-122 | POST `/provisioning/shop` | `provisioning.py` POST `/provisioning/shop`; no frontend caller. | Current-user Admin + reauth; existing-shop form is a no-op and does not call it. NOT IMPLEMENTED. |
| C-123 | POST `/approvals` | `operations.py` POST `/approvals`; no frontend caller. | `APPROVAL_REQUEST`; generic approval creation not wired. NOT IMPLEMENTED. |
| C-124 | POST `/warranty/claims/{id}/supplier-outcome` | `warranty.py` POST supplier-outcome; no frontend caller. | `WARRANTY_DECIDE`/versioned service; UI lacks supplier outcome entry. NOT IMPLEMENTED. |

**Frontend API call-shape accounting:** 89 unique method/path call families were extracted from the 49-module bundle graph. Dynamic purchase/repair/warranty dispatch is expanded into its concrete method/path contracts in the table; C-111–113 call out dynamic operation-family mismatch and stock adjustment. C-114–124 inventory the 11 backend routes with no corresponding active UI. The D matrix therefore has 124 rows: frontend contracts expanded for meaningful concrete routes plus 11 backend-only routes. The backend route catalog itself has 120 registered decorators. The production UI path mismatch is concentrated in the operation router family; no alias path is registered.

**Backend endpoints with no direct UI:** `GET /api/v1/auth/me`; `POST /api/v1/auth/admin/recovery-code`; `POST /api/v1/auth/admin/recover`; `POST /api/v1/auth/change-password`; `PUT /api/v1/admin/users/{user_id}/role`; `POST /api/v1/admin/other-income/{other_income_id}/decision`; `GET /api/v1/permissions/mine`; `POST /api/v1/provisioning/shop`; `POST /api/v1/approvals`; `POST /api/v1/stock-control/damage-loss`; `POST /api/v1/warranty/claims/{claim_id}/supplier-outcome`. The existing-shop form is a no-op rather than a client for provisioning/shop. Route catalog total is 120 decorators; frontend call-family total is 89.

**Shared API client contract:** `client.js#L87-L151` resolves base URL, injects bearer token, uses a 15-second timeout, parses JSON, clears session on 401, and throws normalized timeout/network/status errors. Direct export and health/discovery `fetch` paths bypass parts of this behavior. Most screens use `any`; request/response compatibility is inferred from endpoint source/schema, not generated typed contracts.

## E. Defect and Gap Register

| ID | Severity | Status | Impact / affected workflow | Evidence and safe verification | Missing evidence / recommended next action |
|---|---|---|---|---|---|
| D-01 | Critical | FAIL | Restored database may accept unauthenticated bootstrap under a new branch when external identity lacks branch_code; replacement server may become a second writer. | [`provisioning.py`](../backend/app/api/routes/provisioning.py#L166-L190); [`instance.py`](../backend/app/core/instance.py#L24-L43). Static trace: bootstrap guard reads identity; both DB checks are conditional on the absent field. | No isolated PostgreSQL restore/recovery test. Implement fail-closed identity reconciliation and writer fencing before restore/bootstrap can serve writes. |
| D-02 | High | FAIL | Cashiers with `REPORT_VIEW`/`STOCK_VIEW` can receive gross/net profit and FIFO/purchase unit cost irrespective of hidden controls. | [`reports.py`](../backend/app/api/routes/reports.py#L47-L68); [`repairs.py`](../backend/app/services/repairs.py#L101-L115); [`RepairWorkspace.js`](../frontend/src/features/repairs/RepairWorkspace.js#L190-L205). | No role-response tests were run. Add tests for every report/detail/export response under Cashier and Admin, then enforce response/query masking. |
| D-03 | High | FAIL | Day End, Shift End, Day Start, repair create/list/details/status/payment/finalize/deliver/cancel/parts/warranty and settlement cannot reach their registered route paths. Dashboard combined load rejects. | [`router.py`](../backend/app/api/router.py#L3-L19); [`operations.py`](../backend/app/api/routes/operations.py#L43-L207); active callers [`DayEnd.js`](../frontend/src/features/finance/DayEnd.js#L26-L185), [`RepairWorkspace.js`](../frontend/src/features/repairs/RepairWorkspace.js#L38-L100), [`POSHome.js`](../frontend/src/features/pos/POSHome.js#L203-L207). | No live HTTP check; path composition proves mismatch. Add a route-contract test that compares all bundled path/method pairs to OpenAPI/router registrations. |
| D-04 | High | FAIL | Card/Online purchases are stored as CASH because route drops the field; Cash In Hands subtracts only CASH purchases and expenses, violating all-method calculation. | [`purchases.py`](../backend/app/api/routes/purchases.py#L15-L28); [`PurchaseCreateIn`](../backend/app/schemas/purchases.py#L13-L22); [`PurchaseService.create_purchase`](../backend/app/services/purchases.py#L25-L35); [`ReportService.cash_in_hands`](../backend/app/services/reports.py#L102-L115). | No DB calculation test was run. Add route-to-service payload test and all-method finance fixtures. |
| D-05 | High | FAIL | Retried return, expense/income, repair intake, or cash-in can duplicate business/financial records after timeout. | UI payloads [`ReturnsWorkspace.js`](../frontend/src/features/returns/ReturnsWorkspace.js#L55-L91), `POSHome.js` expense flow around `ExpensesTab`, [`RepairForm.js`](../frontend/src/features/repairs/RepairForm.js#L25-L73), [`DayEnd.js`](../frontend/src/features/finance/DayEnd.js#L108-L120); schemas/services permit missing keys. | Existing idempotency tests for selected flows were not run. Require stable keys for retryable mutations and test identical/conflicting replay at service/API levels. |
| D-06 | High | NOT IMPLEMENTED | Spreadsheet historical import, staging/provenance/approval/stock reconciliation absent; real-shop migration gate unmet. | Searches of `backend/app`, `frontend/src` TSX/JS, and `scripts` found no source-file staging/import flow; [DATA_IMPORT_AND_MIGRATION.md](DATA_IMPORT_AND_MIGRATION.md) describes required steps. | No import acceptance tests possible. Plan a synthetic-data staged importer with reconciliation before any live migration. |
| D-07 | High | FAIL | Session policy contradicts normative 30-minute idle/10-minute reauth; actual idle defaults are 5m Admin/60m Cashier. | [`config.py`](../backend/app/core/config.py#L8-L16); [`deps.py`](../backend/app/api/deps.py#L20-L57); [`reauth.py`](../backend/app/security/reauth.py#L7-L14); `test_session_inactivity.py`. Safe test confirms test codifies old values. | Selected test ran; no boundary/revocation/security acceptance. Align config and implement/test defined reauth window. |
| D-08 | High | FAIL | Admin cannot approve/reject pending expenses or approval requests through current UI: requests omit required `version`; approval route also has wrong prefix. | [`POSHome.js`](../frontend/src/features/pos/POSHome.js#L540-L547); [`admin.py`](../backend/app/api/routes/admin.py#L173-L185); [`operations.py`](../backend/app/api/routes/operations.py#L134-L161). | No HTTP test executed. Include version in both review payloads and route-contract tests. |
| D-09 | High | FAIL | Day/repair/settlement route families are uncallable, blocking cash close, repairs and credit settlement. | See D-03; exact router has no `/operations` prefix. | Same focused route-contract test; do not declare these workflows accepted until API/browser tests pass. |
| D-10 | High | PARTIAL | Restore success is returned after pg_restore/connectivity without Shop/Server Identity verification, old host fencing, or post-restore DB audit. | [`backup.py`](../backend/app/api/routes/backup.py#L74-L94); [`backup/service.py`](../backend/app/backup/service.py#L55-L75); external identity in `instance.py`. | No restore was run. Add isolated restore checks for identity, one-writer state, audit preservation, interrupted restore and failure state. |
| D-11 | High | PARTIAL | Backup retry/remote-verification/close fallback is manual or absent; cloud copy can remain pending indefinitely. | [`backup.py`](../backend/app/api/routes/backup.py#L17-L46), `#L96-L111`; [`backup/service.py`](../backend/app/backup/service.py#L79-L89); close guard in `operations.py#L20-L32`. | No rclone or pg tools executed. Add durable queue worker, object integrity verification, alternate target UX and outage tests. |
| D-12 | High | FAIL | Sale/reprint controls imply thermal printing but no active UI/backend route calls a printer; “reprint” only records a document event. | [`documents.py`](../backend/app/api/routes/documents.py#L29-L44); [`adapters.py`](../backend/app/printing/adapters.py#L7-L55); active `POSHome.js` checkout/reprint handlers. | No printer/hardware test. Wire asynchronous print-after-commit/reprint and test printer failure leaves committed transaction intact. |
| D-13 | High | FAIL | Non-admin expense decision UI omits version; `ApprovalReviewIn.version` is also omitted, so backend rejects stale/missing versions with 409. | Evidence D-08. | Add endpoint tests and refresh/version payload flow; no UI acceptance run. |
| D-14 | Medium | NOT IMPLEMENTED | Existing-shop setup CTA submits branch fields only to `console.log`; no provisioning endpoint or persistence. | [`ServerExistingShopForm.tsx`](../frontend/src/components/ServerExistingShopForm.tsx#L10-L24); backend `/provisioning/shop` exists but is not called. | No browser run needed to see no-op; implement authorized existing-shop workflow only after identity policy exists. |
| D-15 | Medium | FAIL | Export in packaged Tauri client targets relative `/api/v1` on app origin rather than resolved discovered server. | [`POSHome.js`](../frontend/src/features/pos/POSHome.js#L355-L370); [`client.js`](../frontend/src/api/client.js#L87-L151); build script sets relative API base. | No LAN export test. Route exports through shared client/resolved base and verify authorization/errors with a discovered host. |
| D-16 | Medium | PARTIAL | Purchase UI exposes payment method but route does not persist it; financial reports misclassify purchase outflows. | D-04. | Same route/service test and finance reconciliation. |
| D-17 | Medium | PARTIAL | Expense/other-income rows can remain pending forever because Admin list/decision UI covers Expense only; decision endpoint for other income is not connected. | [`POSHome.js`](../frontend/src/features/pos/POSHome.js#L487-L547); [`admin.py`](../backend/app/api/routes/admin.py#L143-L200). | No approval workflow test. Add pending other-income list and audited versioned decisions. |
| D-18 | Medium | PARTIAL | Admin password reset marks cashier for forced change, but active entry flow has no `must_change_password` screen; change-password route has no UI client. | `auth.py#L73-L74`, `admin.py#L219-L229`, `Login.js`; bundle API inventory. | No forced-password test. Add auth state workflow and test no normal POS access until changed. |
| D-19 | Medium | PARTIAL | Manual fallback at startup is exposed before authenticated Admin identity; text label is not an authorization control. | `DiscoveryStatus.js`; `main.tsx` boot branch; `SettingsPanel.js` protects only Settings path. | No browser role test. Clarify trusted local setup authority and gate privileged manual configuration. |
| D-20 | Medium | PARTIAL | Saved client `server_reference` is overwritten by any verified candidate; resolver stops at first verified server and does not reject duplicate Shop Identity. | [`discovery.js`](../frontend/src/services/discovery.js#L56-L112); [`machine-config.js`](../frontend/src/services/machine-config.js#L210-L244); [`mdns_discovery.rs`](../desktop/tauri/src/mdns_discovery.rs#L18-L57). | Mocked tests inspected but not run; no physical multi-server test. Pin/reconcile identity, enumerate all candidates, fail closed on duplicates. |
| D-21 | Medium | PARTIAL | Purchase/Item multi-request UI saves can partially commit (item commits before warranty-default/barcode), leaving frontend error despite persisted base item. | `POSHome.js` ItemMaster save handler around lines 435-470; item endpoints each commit separately. | No partial-failure test. Provide transactional workflow or explicit recovery/reload state and test second-request failure. |
| D-22 | Medium | PARTIAL | Reports comparison computes same-length previous interval, not guaranteed previous calendar month; custom/date preset semantics differ from label. | [`reports.py`](../backend/app/api/routes/reports.py#L47-L55); `POSHome.js` report presets. | No calendar-boundary test executed. Define and test comparison semantics. |
| D-23 | Medium | NOT IMPLEMENTED | Notification icon and global quick-search are non-functional controls; screens show no search workflow on global field. | [`DashboardLayout.js`](../frontend/src/layouts/DashboardLayout.js#L46-L54). | Browser check not needed for absent handlers; remove/disable or connect controls in follow-up. |
| D-24 | Medium | PARTIAL | UI tests import TSX while production bundle resolves feature `.js` siblings; source/test divergence can leave shipped behavior untested. | [`index.html`](../frontend/index.html#L1); temp source map from Vite build; `vitest.config.ts`. | Vite bundle test verified module selection; add parity/guard test and run behavioral tests against production-resolved modules. |
| D-25 | Medium | NOT VERIFIED | No live DB revision, production env, branch data, migration preconditions or target configuration inspected (intentionally). | `alembic/versions` source ends at 0031; no DB command executed. | Record actual staging DB revision and run safe migrations/rollback only in authorized disposable staging. |
| D-26 | Low | FAIL | A focused existing contract test fails because it expects `CASHIER-LAPTOP-IP` in `.env.example`, while file contains relative `/api/v1`; current test suite is internally inconsistent with documented no-hardcoded-IP direction. | `backend/tests/test_frontend_contract.py#L19-L23`; `frontend/.env.example`. Executed in this audit. | Align test expectation with current intended config; no source was changed. |
| D-27 | Low | PARTIAL | Stock view silently swallows load errors and list surfaces lack general paging/sorting; limits can hide older records. | Active `POSHome.js` StockTab; route limits in inventory/admin/documents. | No browser usability run. Add visible errors and pagination where business volume requires it. |
| D-28 | Low | NOT VERIFIED | Physical printer, scanner, Windows account/firewall/CSP, MSI/NSIS artifacts and installation/update behavior not tested. | [`tauri.conf.json`](../desktop/tauri/tauri.conf.json#L13-L26) has `csp: null`; scripts available but no packaging. | Target Windows/hardware acceptance and security review required. |
| D-29 | Low | PARTIAL | API client uses localStorage bearer session and fixed timeout; local health polling has no timeout/readiness DB check. | `client.js#L87-L160`; `DashboardLayout.js`. | No connectivity browser testing. Validate local error states and readiness semantics. |
| D-30 | Low | PARTIAL | Frontend currently uses broad `any` response types and direct fetch for exports; schema drift is not caught by TypeScript. | `POSHome.js`; `api/client.js`; backend Pydantic schemas. | Generate/maintain typed request/response contracts and static contract test. |

**Severity ordering rationale:** data-loss/recovery and single-writer safety first; financial correctness and retry behavior next; authorization/cost confidentiality and session controls next; core operations continuity; then printing, import UX, and lower-risk usability. D-03 and D-09 describe the same route-root defect from contract and business-impact perspectives; they are not two independent bugs.

## F. Tests and Acceptance Evidence Matrix

### Executed in this audit

| Check | Exact command | Result and scope |
|---|---|---|
| Backend focused pytest | `$env:PYTHONDONTWRITEBYTECODE='1'; & 'backend/.venv/Scripts/python.exe' -B -m pytest -p no:cacheprovider backend/tests/test_session_inactivity.py backend/tests/test_frontend_contract.py` | **4 passed, 1 failed**, exit code 1. Failure: `test_frontend_env_example_does_not_hardcode_shop_ip` expects `CASHIER-LAPTOP-IP` absent/present contract text inconsistent with actual `.env.example`; session configuration assertion passed. Bytecode and pytest cache disabled. |
| Frontend TypeScript check | `Push-Location frontend; & './node_modules/.bin/tsc.cmd' --noEmit -p tsconfig.json --pretty false; Pop-Location` | **Passed, exit code 0.** No emitted build artifacts. |
| Vite production-mode bundle | `Push-Location frontend; $out = Join-Path $env:TEMP 'ltpos-parity-audit-dist'; & './node_modules/.bin/vite.cmd' build --outDir $out --emptyOutDir --sourcemap true; Pop-Location` | **Passed, Vite 7.1.7, 49 modules, 5.09s.** Output/source map stayed in OS temp; used to establish active module extensions. A first attempt from repo root failed before transforming source because `index.html` was not at that cwd; rerun from `frontend` passed. This is not the package script `npm run build` or a Tauri build. |
| PDF tool availability | PowerShell `Get-Command pdftotext, mutool, qpdf` and Python `importlib.util.find_spec` for `pypdf`, `PyPDF2`, `fitz`, `pdfminer` | No extraction tool/module found; no package installed. PDF contents remain NOT VERIFIED. |
| Static source counts | Vite source map/TypeScript parser and route decorator scan | 150 interaction IDs enumerated below; 89 bundled frontend call-shape families; 120 backend route decorators; 31 source migration revisions. These are inventory counts, not test results. |

### Inspected, not executed

- Backend: `test_api_contracts.py`, `test_provisioning.py`, `test_discovery.py`, FIFO/replay, sales/idempotency, return/refund/exchange, purchase correction, repair/warranty, day finance/reload/approval, report/target, backup/restore, immutability, and deployment tests. Many use application DB/session configuration; they were not executed to avoid any uncertain live database or mutation. Their filenames/source are coverage evidence only.
- Frontend: client boot, startup discovery, manual-server, machine-config, discovery, Vitest and Playwright smoke source. Not executed in this audit; source tests use mocks in discovery-focused cases.
- Migrations, Alembic heads/SQL, live database contents/revision, DB rollback, import, restore, backup creation, and transactions: not run.

### Acceptance not performed

| Acceptance class | Status | Evidence needed |
|---|---|---|
| Manual browser checks | NOT VERIFIED | Run against isolated synthetic staging server after correcting route contracts; exercise errors, empty/loading/success and every workflow. |
| Real database/integration | NOT VERIFIED | Confirm disposable staging DB explicitly, then run service/API concurrency, audit, permission and financial reconciliation tests. No production DB was queried. |
| Physical printer/scanner | NOT VERIFIED | Target Windows receipt/A5 printers, disconnect/reconnect after commit, barcode scanner and separate audited reprint. |
| Multi-laptop/LAN | NOT VERIFIED | Actual two-plus device mDNS/firewall, router/DHCP change, client reconnect, owner client powered off and concurrent use. |
| Backup/restore disaster recovery | NOT VERIFIED | Isolated PostgreSQL VERIFIED-only restore, safety backup, wrong/lost key, interrupted restore, replacement server, identity reconciliation and split-brain fence. No destructive restore was run. |
| Windows desktop/package/release | NOT VERIFIED | Build/install MSI/NSIS on target Windows with required toolchain; inspect signature/hash/CSP/firewall/account configuration and upgrade path. |

No test result from `PROJECT_STATUS.md` is represented as newly executed. No full suite, npm package install, destructive check, migration, import, restore, or real transaction was run. The temp bundle and no-emit test left no project outputs by command design; no other project file was intentionally changed.

## G. Prioritized Remediation Plan

1. **Add the missing-identity bootstrap regression test and fail-closed recovery guard.** Use only an isolated synthetic DB fixture. Then implement Admin-only identity reconciliation and old-server fencing; validate verified-only restore and one-writer behavior without production data.
2. **Build the controlled historical import and reconcile before acceptance.** Synthetic staging, row provenance, validation/mapping/duplicate review, Admin preview/approval, repeat-safe transactional batches, rollback, and stock/financial totals.
3. **Complete durable backup transport and verified recovery.** Durable retry queue, remote integrity verification, alternate close fallback, key custody, immutable post-restore audit, and replacement-server identity reconciliation.
4. **Correct payment-method persistence and cash calculations.** Forward `payment_method` through purchase route/service; include all approved payment-method outflows in Cash In Hands; add card/online purchase and expense calculation tests.
5. **Make retryable financial mutations idempotent end to end.** Add stable request keys and payload-hash replay/conflict tests to return creation, expenses/other income, repair intake and cash-in; keep UI key stable across timeout and rotate only after success.
6. **Add Admin/Cashier response-contract tests and mask sensitive responses.** Start with `/reports/comparison`; then cover `/reports/stock-age`, `/reports/purchases`, repair detail and exports. Run against isolated fixtures, not a shop DB.
7. **Bring session policy into line with REQ-2.02.** Set 30-minute idle consistently, define and implement the 10-minute critical reauth freshness window, and test role changes/revocation/boundaries without exposing credentials.
8. **Fix all operation-router contract paths/methods in one bounded task.** Align active bundled Day/Repair/Settlement/Approval calls with registered routes; include required version fields and add a static contract check plus focused API tests.
9. **Implement pending other-income review and forced password-change UI.** Connect Admin list/decision/version path and ensure `must_change_password` gates normal POS navigation.
10. **Make print an explicit post-commit workflow.** Use adapter/print queue only after sale commit; record reprints separately; test disconnected printer does not change persisted transaction state.
11. **Build one role-aware installer and run target acceptance.** Guided connect/create/restore; supported upgrade compatibility; actual Windows packaging and all release-checklist scenarios on staging and physical devices.
12. **Resolve lower-risk UX/quality gaps.** Remove or implement notifications/global search; surface stock errors; paginate capped lists; correct previous-period semantics; maintain typed API contracts; review CSP and packaged security posture.

### Audit boundaries and unresolved comparisons

- `PDF-CMP-01` — **NOT VERIFIED**: v2.0 PDF located but no safe local text extraction tool was available. Provide extracted PDF text or an approved reader in the audit environment before comparing PDF wording. No PDF rule was guessed.
- Accessible maintained docs were read: README, REQUIREMENTS, PROJECT_STATUS, ARCHITECTURE, OPERATIONS_AND_RECOVERY, DATA_IMPORT_AND_MIGRATION, RELEASE_CHECKLIST. `REQUIREMENTS.md` remained normative as confirmed by the user. The accessible docs consistently warn that physical/recovery scenarios require target acceptance; no contrary test claim was adopted.
- This report is a source-and-local-check audit, not authorization to alter live data or to call the product secure, recoverable, or production-ready.
