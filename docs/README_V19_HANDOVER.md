# Lovely Tech POS — V19 Frontend Cash/Day + Admin Controls Hardening

Date: 2026-10-02

## Scope
Frontend-only hardening on top of V18. Backend source/contracts were not modified.

### Cash / Day
- Day Start denomination total must match opening cash before submit.
- Opening cash correction now sends the backend-required Day session `version`.
- Existing Admin re-authentication remains required for opening correction and Day reopen.
- Physical denomination count remains required before Day End.
- Verified-backup gate remains enforced by backend before Shift End / Day End.

### Admin controls
- User discount-limit update now sends the backend-required user `version`.
- Discount limit is validated client-side to 0–100%.
- Save button is busy-guarded and shows current user version for safer concurrent editing.
- Existing Admin re-authentication for role permission changes is preserved.
- Existing expense approval / other-income entry / supplier / target / audit controls are preserved.

## Validation
- Source structure inspected and changed contracts cross-checked against backend routes/schemas.
- Full Vite build was not run because this environment does not contain `frontend/node_modules`.
- Backend source was not changed.
