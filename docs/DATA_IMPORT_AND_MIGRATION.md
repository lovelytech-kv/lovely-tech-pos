# Lovely Tech POS — Data Import and Migration

## Historical spreadsheet import requirement

The final historical migration must support products, purchase history, sales history, and customer/history data from spreadsheets. This is a pre-release requirement. The current status audit did not find an application import workflow in the inspected backend, frontend, or scripts; do not treat a spreadsheet upload screen or a direct SQL load as a complete import.

## Required controlled workflow

1. **Source inventory:** identify each spreadsheet, owner, export date, sheet, columns, date/number formats, encoding, and known omissions. Preserve originals read-only.
2. **Staging:** load candidate rows into an isolated staging area, never directly into live operational tables. Retain a source file identifier and row number for provenance.
3. **Validation:** check required fields, valid dates, quantity/currency formats, branch assignments, referential links, and domain constraints. Report rejected and ambiguous rows; do not invent missing values.
4. **Mapping:** map source products/customers/document references and payment methods to canonical records. Keep an auditable mapping table for source IDs and target IDs.
5. **Duplicate detection:** identify duplicate items, invoices, customers, line items, serials, and overlapping histories. Require an explicit resolution for collisions; never reuse invoice numbers.
6. **Business-rule validation:** validate stock movements, costs/prices, partial returns, payments, warranties, and branch ownership against current rules.
7. **Admin preview and approval:** show counts, exceptions, financial totals, and stock reconciliation before approval. Preserve who approved and when.
8. **Approved import:** apply records using transactional, repeat-safe batches and backend validations. Do not bypass service-level rules with uncontrolled bulk SQL.
9. **Verification/reconciliation:** compare source and imported counts, totals, date ranges, documents, customer links, and per-item stock. Record differences and obtain sign-off.
10. **Rollback/recovery:** retain a verified pre-import backup and a documented recovery point. A failed import must not leave a partially approved dataset presented as complete.

## Preserve and reconcile

Preserve original dates, references/invoice numbers, quantities, costs/prices, payment/customer details where available, and source provenance. Distinguish source facts from inferred mappings. Missing historical records must remain missing/unknown, not be fabricated.

For each stock item/branch, reconcile:

```text
opening stock
+ historical purchases
- historical sales
+ returns and approved adjustments
= current stock
```

Also reconcile sales and payment totals, return/refund totals, purchase totals/costs, customer balances, and document number conflicts. Explain each approved discrepancy.

## Database schema migrations

- Use Alembic migrations for schema evolution. Review the exact target database and deployed revision before applying.
- Take and verify a backup before a production migration; use a staging database first.
- Confirm a single intended migration head, generate/check migration SQL where appropriate, and test upgrade behavior against a representative database.
- Migrations must preserve existing business data and fail explicitly when unsafe duplicates or invalid states exist. Do not silently rewrite or discard records to make a migration pass.
- Keep upgrade/downgrade behavior and irreversibility documented. Never run reset/drop/recreate against production as a routine migration strategy.
- Current source includes migrations through revision `0031_alembic_version_id_capacity`; the actual deployed database revision was not checked in the current audit.

## Import acceptance gates

Before real-shop release, test clean import, duplicate input/retry, malformed rows, ambiguous mapping, partial failure, backup/restore, branch isolation, numeric precision, history lookup, and stock/financial reconciliation. Require Admin approval and signed reconciliation results.
