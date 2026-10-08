# Lovely Tech POS — Frontend Returns, Exchange & Warranty Batch

## Scope

This batch continues from V15 and changes the frontend only. Backend source and API contracts are unchanged.

### Returns / Exchange
- Replaced the compact inline return screen with a dedicated workspace.
- Find a completed sale by sale ID or invoice number.
- Select per-line return quantities and item condition.
- Require a return reason before completion.
- Show the estimated selected refund amount.
- Complete the return through the existing `/returns` endpoint.
- Load a return and display refund total, paid total, remaining refund and payment history.
- Record cash/card/online refund payments using the existing idempotency-key contract.
- Prevent the UI from submitting a refund larger than the remaining refund.
- Link a completed return to a replacement sale through the existing `/returns/exchange` endpoint.
- The replacement sale remains a normal Sales workflow; the exchange screen only links the already-created replacement sale.

### Warranty
- Replaced the compact inline warranty screen with a dedicated workspace.
- Serial/IMEI lookup and warranty-number lookup show exact stored dates and status.
- Warranty calculator supports NONE, DAYS, MONTHS, CHECKING ONLY and CUSTOM.
- Claim creation supports item, quantity, optional ProductWarranty ID and notes.
- Claim list displays the actual backend `holding_quantity` value and optimistic-lock version.
- Admin claim decisions send the current claim version.
- Supplier outcomes support replacement, shop-held damage and customer-keeps-item with a quantity field.
- Manual warranty registration remains explicitly marked as an Admin exception.

## Backend freeze
No backend files were intentionally changed in this batch.

## Verification
- V15 source was used as the base.
- ZIP integrity check passed.
- Static TypeScript invocation was attempted. Full compilation remains blocked by the supplied environment because frontend `node_modules` are absent. Reported diagnostics for the new files are dependency-resolution/JSX-runtime errors caused by that missing dependency tree; no new source syntax error was reported.
- Full Vite build and Playwright remain pending until dependencies are installed in the development/laptop environment.
