# Lovely Tech POS — Data Import and Migration

## Historical spreadsheet import requirement

The final historical migration must support products, purchase history, sales history, and customer/history data from spreadsheets. This is a pre-release requirement. The current status audit did not find an application import workflow in the inspected backend, frontend, or scripts; do not treat a spreadsheet upload screen or a direct SQL load as a complete import.

## Packet 3 — Backend Upload & Preview API (staged)

The Packet 3 implementation provides a **staging and preview only** backend API. It uploads, validates, and stages spreadsheet rows into isolated staging tables. It does **not** create or update any operational business records (products, purchases, sales, payments, stock movements, FIFO layers, customers, or suppliers).

### Authentication & authorization

- All endpoints require a bearer session token (authenticated user).
- Upload and preview require the `IMPORT_MANAGE` permission. ADMIN users bypass the permission check but still must pass the shop-identity write-gate (POST only, restore state must be READY and shop identity must be PRESENT).
- Unauthenticated requests receive 401; authenticated non-ADMIN users without IMPORT_MANAGE receive 403.
- Cashiers are explicitly blocked from upload and preview.

### Supported import types & file formats

| Import type | Pydantic schema (Packet 1) | Required CSV columns |
|---|---|---|
| Item | `ImportItemRecord` | ITEM CODE, DESCRIPTION |
| Purchase | `ImportPurchaseRecord` | DATE, ITEM CODE, UNIT PRICE, QUANTITY |
| Sale | `ImportSaleRecord` | DATE, ITEM CODE, SALE PRICE, QUANTITY |

- **File format**: CSV only (UTF-8). The project does not include `python-multipart` or `openpyxl`, so multipart and Excel formats are not supported in this packet.
- Upload is sent as a raw request body with `filename` and `import_type` supplied as query parameters.
- **File size limit**: 10 MB (enforced via Content-Length header and actual body size).
- **Row limit**: 50,000 rows per file.

### Endpoints

#### POST /api/v1/import/upload

Query parameters:
- `filename` — source filename (must end in `.csv`, max 255 chars).
- `import_type` — one of `ITEM`, `PURCHASE`, `SALE` (required; 422 if missing, 400 if invalid value).

Request body: raw CSV bytes.

Responses:
- 200 — successful staging; returns `{batch_id, total_rows, valid_rows, invalid_rows, message}`.
- 400 — unsupported extension, empty file, malformed CSV, invalid encoding, duplicate/colliding headers, too many rows, or rows exceeding size limit.
- 401 — unauthenticated.
- 403 — authenticated but insufficient permission (non-ADMIN without IMPORT_MANAGE).
- 409 — shop identity not established (POST write-gate).
- 413 — file exceeds 10 MB.
- 500 — internal server error; partial writes are rolled back.

Header collision detection: duplicate column names after whitespace trimming are rejected before a batch is created.

Validation: each CSV row is validated independently using the Packet 1 Pydantic schema for the selected import type. Valid rows are stored with `validation_status = "VALID"`; invalid rows are stored with `validation_status = "INVALID"` and a sanitised error message in `error_details`. Source row numbers are 1-based with row 1 reserved for the header (first data row is row 2).

#### GET /api/v1/import/preview/{batch_id}

Query parameters:
- `limit` — page size (default 50, max 500, min 0).
- `offset` — page offset (default 0, min 0).

Responses:
- 200 — batch metadata, row counts, invalid-row sample (capped at 50), and paginated preview of staged rows.
- 401 — unauthenticated.
- 403 — insufficient permission.
- 404 — batch not found.
- 422 — invalid pagination parameters.

Response fields: `batch_id`, `import_type` (looked up from staging rows), `filename`, `status`, `uploaded_at`, `uploaded_by`, `total_rows`, `valid_rows`, `invalid_rows`, `invalid_details` (list of `{row_number, error}` capped at 50), `preview_data` (bounded by `limit`/`offset`), `pagination` (`{limit, offset, total}`).

### Staging transaction safety

- A new `ImportBatch` row is created first, then staging rows are added within the same transaction.
- On any exception during staging, `db.rollback()` is called and a 500 response is returned. No partial batch or partial rows persist.
- A malformed file (unparseable CSV, invalid encoding, duplicate headers, no data rows) is rejected **before** any batch is created, so no misleading batch record is left behind.
- Staged batches use status `PENDING_APPROVAL` (the existing model default). Approval/commit to operational tables is a subsequent packet.

### Idempotency & limitations

- **No idempotency**: repeated uploads of the same file create distinct `ImportBatch` records. There is no deduplication mechanism on the import batch or staging rows. This is a known limitation for a subsequent packet.
- Internal file paths, credentials, raw exception messages, and unrelated user data are never returned in responses.
- Row-level error messages are sanitised: Pydantic validation errors are formatted as `field: message` without exposing input values or stack traces.

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
