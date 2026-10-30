# Requirements v2.0 – clause-by-clause traceability

Status: **T** = covered by an automated test (real PostgreSQL / browser) · **C** = implemented in code, found by code review, no dedicated test · **P** = partly · **H** = needs shop hardware / Windows (cannot be verified in the cloud). Backend suite 332 passed, frontend 92 passed.

| § | Clause | Status | Where / evidence |
|---|---|---|---|
| 01 | Offline-first LAN, branch-aware, one DB server | C, H | `branch_id` on all tables; LAN in DEPLOYMENT_LAN.md; two-laptop LAN needs the pilot |
| 01 | Atomic transactions | T | test_e2e_requirements, test_sale_return_idempotency |
| 02 | Cashier/Admin split, no cost/supplier/profit for Cashier | T | test_e2e_requirements, `smoke_api.py` |
| 02 | Own-sales reprint for cashier | T | test_e2e_documents_reprint |
| 02 | Admin auto-lock 5 min / Cashier 1 h, lockout after wrong passwords | T | test_session_inactivity; login lock in `auth.py` (C) |
| 02 | Cashier password reset needs Admin + forced new password | T | test_e2e_forced_password_change, browser sweep |
| 02 | Admin recovery with one-time offline code | C | `services/recovery.py`, `/auth/admin/recover` |
| 02 | Re-auth for critical Admin actions | T | stock adjust, damage, restock, void, payment reversal, restore tests |
| 02 | Immutable audit log, Admin only | T | test_audit_immutability |
| 03 | Separate tabs; colour meaning; double-click protection | C | `POSHome.tsx`; idempotency keys (T) |
| 03 | Search by code/description/brand/model/barcode/category/IMEI; in-stock first; negative warning | T/C | test_e2e_serialized, test_e2e_requirements_audit2 |
| 04 | Sequential LVT item code, never reused; imported codes kept | T | test_numbering_format, test_import_script |
| 04 | Multiple barcodes; optional master price; custom sale price | T | test_item_master_warranty |
| 04 | IMEI unique, duplicate sale blocked | T | test_e2e_serialized |
| 04 | Compatible models, display quality variants | T | test_e2e_requirements_audit2 |
| 04 | Warranty copied into sale record | T | test_warranty_sale_override |
| 05 | Movement-based stock, exact FIFO lots | T | test_fifo_engine, test_fifo_replay |
| 05 | Negative stock allowed; later purchase reconciles | T | test_stock_recovery, audit tests |
| 05 | Admin-only stock adjustment with reason; positive uses latest lot cost | T | test_e2e_serialized_stock_control |
| 05 | Purchase cost/qty/date correction recalculates FIFO + audit | T | test_e2e_requirements_audit |
| 05 | Returned stock keeps cost lineage | T | test_return_refund_payment |
| 05 | Internal-use movement | P | no separate type: record it as Damage/Loss or Adjustment with reason "internal use" (traceable, in audit) |
| 06 | Sale flow, invoice numbers never reused after void | T | test_e2e_sale_void |
| 06 | Cash/Card/Online, split payment | T | test_sales_service |
| 06 | Discount limit per user, excess needs Admin approval | T | test_e2e_discount_approval + browser |
| 06 | Credit sale Admin-only, outstanding tracked | T | test_credit_settlement_*, browser |
| 06 | Printer failure never rolls back a sale; reprint is an event | T/H | test_printing*; real printer = pilot |
| 07 | 7-day return window, Admin override, partial returns | T | test_sale_return_exchange_version_lock |
| 07 | Return charge = separate income, in profit | T | test_return_refund_payment |
| 07 | Exchange = one return + separate new sale, drawer example (+700) | T | test_e2e_requirements |
| 07 | Good return restocks; damaged return -> Damage/Loss | T | test_return_refund_payment |
| 07 | Admin reverses damage through audited restock | T | **new** test_e2e_damage_restock (+ Admin panel "Damage / Loss Records") |
| 07 | "Cashier marks exchange damage, Admin finalizes" | P | damage is effective at once (booked APPROVED); Admin can reverse by restock. No separate pending state |
| 08 | Cashier purchase without cost; stock up immediately; no payment method | T | test_e2e_purchase_no_payment_method, test_purchase_contract |
| 08 | Admin pending cost, item-by-item, immutable lots, controlled correction | T | test_locked_completion, audit tests |
| 09 | REP-000001 IDs, statuses, form fields | T | test_e2e_repair_day_warranty |
| 09 | Parts deduct FIFO; good part restores lot; damaged part -> Admin review | T | test_e2e_repair_day_warranty |
| 09 | Advance + final payments, split, delivery with outstanding needs Admin | T | test_e2e_repair_day_warranty |
| 09 | Cancellation: parts back, payments only by explicit reversal, never deleted | T | **new** reversal endpoint + Admin button in repair payments; test_e2e_requirements_audit2 |
| 09 | Repair warranty separate | C | `RepairWarranty` model |
| 10 | Warranty types NONE/DAYS/MONTHS/CHECKING/CUSTOM | T | test_warranty_calculator |
| 10 | Claim by cashier; Admin decides supplier claim or damage/loss; WARRANTY_REPLACEMENT; rejection rules | T | test_e2e_repair_day_warranty, browser |
| 10 | Manual invoice inside sale; lost-bill search by invoice/manual ref/IMEI/customer/item/date | T | test_e2e_requirements_audit |
| 11 | Day Start denominations; opening correction Admin-only | T | test_day_finance_validation |
| 11 | Drawer formula; card/online excluded; purchases/expenses not in drawer but in Cash In Hands | T | test_cash_only_calculations |
| 11 | Other Cash In; Reload once per day, brand-wise, cash-only | T | test_reload_once_per_day |
| 11 | Day End expected/actual/difference/reason; Admin reopen | T | test_e2e_repair_day_warranty |
| 11 | Shift End vs Day End; 1 h auto-close; Admin Continue | T | test_e2e_repair_day_warranty |
| 11 | Backdated sale keeps original date + entry timestamp | T | test_e2e_requirements_audit |
| 12 | Expense categories (+Admin adds); cashier entries pending; pending excluded | T | test_expense_other_income_*, browser |
| 13 | Customer history; settlements are payment events, not revenue | T | test_customer_history_warranty, browser |
| 14 | Daily/Monthly/Yearly/Custom, PDF + Excel | C | `reports.py` (openpyxl/reportlab); open the exported files at the pilot |
| 14 | Cash/Card/Online totals; month comparison | T | test_e2e_requirements_audit |
| 14 | Targets (6 types), cashier sees no numeric profit target, history | T | test_target_snapshots, browser |
| 15 | Backup create/encrypt/upload/verify; failed = not a restore point | T | test_backup, test_auto_backup |
| 15 | Close needs backup, retry, then alternate target, later Drive sync | T | test_auto_backup |
| 15 | Cashier sees status + last time only | T | **new** test (backup status) |
| 15 | Restore Admin-only: safety backup, confirm, integrity, audit; interrupted restore never "success" | T | test_restore_runner, rehearsal on real-size data |
| 15 | Real Google Drive upload | H | pilot |
| 16 | Audit coverage, old->new values | T/C | audit tests; spot-checked, not every action individually |
| 16 | Profit formula, FIFO cost, payment method irrelevant | T | test_e2e_requirements, history import tally with the sheets |
| 17 | Idempotency, versions/stale-record protection, no hard deletes | T | test_concurrency_hardening, test_history_immutability |
| 17 | Power failure mid-commit | C | PostgreSQL transactions; not simulated |

## Changes made during this audit
Sale void (Admin), stale cost after correction, lost-bill search, month comparison, compatible models, damage/loss approval re-auth, repair payment reversal (+drawer follows), cashier backup status, **damage restock**, forced password change after reset, IMEI-safe stock adjust/damage.

## Still open
Hardware/Windows/LAN/Drive (H rows) and the two **P** rows above. Everything else on the list is implemented; "C" rows are worth a quick look during the pilot.
