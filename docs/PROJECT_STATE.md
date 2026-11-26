# LOVELY TECH POS — MASTER PROJECT STATE

**Last Updated:** 2026-11-26 (after 3B-4c, pre 3B-4b)
**Version:** Backend 0.6.0 | Migrations: 0046_item_cost_review_threshold (head)
**Status:** Sessions 1A→3B-5 merged. 3B-4c pending merge. Next: 3B-4b (image + low-stock) + 3B-4b-backup (V3 backup for images). System NOT live.

---

## 1. PROJECT OVERVIEW

**Product:** Mobile phone repair shop POS (offline-first, LAN, 1 server + 1-3 client laptops, Windows Tauri).
**Owner:** Lovely Tech (Sri Lanka). **System NOT live** — shop using manual method. No real customer data. Production DB `lovely_tech_pos` = dev/test data.
**Stack:** FastAPI + Python 3.13 + PostgreSQL 18 + SQLAlchemy 2 + Alembic | React 19 + Vite 7 + Tailwind v4 + TS 5.9 | Tauri 2.

---

## 2. LOCATIONS

**Repo:** https://github.com/lovelytech-kv/lovely-tech-pos (main = `9bcb269`)
**Local:** `C:\lovely-tech-pos\`
**Docs:** `docs/PROJECT_STATE.md` (this file), `docs/audit-2026-11-17.md`
**Backup:** `C:\lovely-tech-pos-backups\` (chat exports, dumps), `C:\ProgramData\LovelyTechPOS\backups\` (.ltbak), `C:\ProgramData\LovelyTechPOS\wal_archive\` (WAL), `C:\ProgramData\LovelyTechPOS\pitr_base\` (PITR base)
**Item images (planned 3B-4b):** `C:\ProgramData\LovelyTechPOS\item_images\`
**Test DB:** `lovely_tech_test15` (`.env` points here)

---

## 3. GIT BRANCH STATE

| Branch | HEAD | Status |
|---|---|---|
| `main` | `9bcb269` | 3B-5 series merged (40 commits) |
| `fixes-3b4c` | `109783e` | 3B-4c (dead search removal) — **pending merge** |
| `security-session-1` | old | historical, no action |
| `purchases-redesign-3b5` | `833d2e9` | 3B-5d, merged to main |

**Next:** merge `fixes-3b4c` → main, then create `image-upload-3b4b` for image work.

---

## 4. COMPLETED SESSIONS

### Session 1A + 1B + 2 + 3A — Security Hardening (merged `efbf011`)
**29 fixes from audit (42 findings total).**
- 1A (13 findings): C1 documents search, H1 login race, H3 logout scope, H4 absolute expiry, H5+H12+M19 password revoke, H6 session settings reauth, H11 recovery atomic, M18 code scope, M1 no session lock, M16 readable 422, L2 token strip
- 1B (6 fixes): H2 role reauth, H7 LTPOS_TRUST_LAN flag, H8 approval replay, H9 setup localhost+lock, H16+H18 XSS chain (escapeHtml + token sessionStorage), M7 APP_ENV validation
- 2 (12 fixes): H10 FIFO race, H13 pg_restore engine dispose, H14 CLIENT fail-closed, H15 report export routing, H17 AbortSignal timeout, M8 manual server persist, M9 repair idempotency, M10 return idempotency, M12+M13 sales sequence guards, M14 identity timeout, M15 promise cache
- 3A (7 fixes + emergency): E6 reports auto-load, E11 returns search, E4 offline error, C6 cashier read-only, Receipt (shop name + logo), E3 backup retry, E2 add item button

### Session 3B-1 (merged `acd3093`)
E2-nav (Items tab label), Returns condition selector, Returns Enter key, Cashier Profit hidden, B1 lockout message (HTTP 423), D6 404 (favicon), TEST_* cleanup script (not run)

### Session 3B-2 (merged `b51bb40`)
**POS Customer Flow:** CustomerPickerModal, quick-add form, SalesTab customer strip, receipt customer line, history filter, auto-print line items, cashier admin options hidden

### Session 3B-3 (merged `0d04c4b`)
**UI Foundation:** Design tokens (spacing/typography/radius/shadow), collapsible sidebar (default collapsed), AppHeader (active tab name + date/time 24h), receipt footer "Software by Lovely Tech · {phone}", header bug fix (`item.key` not `item.label`)

### Session 3B-4 (merged `3197fd5`)
**Inventory Redesign:** Card grid (Square/Loyverse style), search/filter, grid/list toggle, modal form, header clock 12h prominent. **Emergency fix bundled:** purchases.payment_method schema drift (test15 + prod ALTER applied)

### Session 3B-5 + 3B-5b + 3B-5c + 3B-5d (merged `9bcb269`, 40 commits)
**Purchases Redesign + Role Logic + CRUD:**
- Migration 0046: `items.buy_cost`, `items.needs_admin_review`, `items.low_stock_threshold`, partial index
- Qty bug fix (frontend staging → per-line input)
- Purchases full redesign (line entry, history, detail, remove-line, quick-add supplier)
- Role buy cost: cashier hidden, admin visible, `needs_admin_review` flag logic
- Admin review queue: dashboard tile (always visible) + Admin panel + `GET /items/pending-review` + `PATCH /items/{id}/review`
- Inline category/item_type creation
- Categories/Types CRUD (edit + delete with 409 guards)
- Items soft-delete (with stock/pending guards)
- Duplicate name blur check
- History search by item
- Queue tiles promoted to first 2 admin positions + widget renamed
- **Smoke: 8/8 PASS**

### Session 3B-4c (branch `fixes-3b4c`, HEAD `109783e` — **PENDING MERGE**)
Dead search bar removed from `DashboardLayout.tsx:153` + dead Ctrl+K handler + CSS cleanup (10 locations). Dist rebuilt (1.22 MB). tsc + build pass.

---

## 5. REMAINING ROADMAP

| Session | Scope | Est. | Priority |
|---|---|---|---|
| **Merge 3B-4c** | `fixes-3b4c` → main | 2 min | 🔴 NOW |
| **3B-4b** | Image upload UI (optional per item) + card image display + low_stock_threshold consume in grid (color-coded chips) | ~3 hrs | 🔴 HIGH |
| **3B-4b-backup** | `.ltbak` V3: pg_dump + tar.gz(images) in Fernet payload. V2/V1 read preserved. Restore extracts images. **MUST merge with 3B-4b** | ~2-3 hrs | 🔴 HIGH |
| **Combined test chat** | Full verification 3B-5 + 3B-4c + 3B-4b + 3B-4b-backup (~50 tests) | ~1-2 hrs | 🔴 HIGH |
| **3C** | Audit mediums (M2-M5, M11, M17, M20, M21) + Invoice/Receipt Template Editor (80mm/A4, header/footer, logo, live preview, locked "Software by Lovely Tech" footer) | ~6-8 hrs | 🟡 MED |
| **3D** | Final UI polish across all tabs + Category Manager move to Items workspace + Item Type Code simplification + soft-delete reactivate UI + low-stock threshold grid consume + design tokens across remaining tabs | ~4-5 hrs | 🟡 MED |
| **Final regression** | Full tab walkthrough + audit re-check | ~2 hrs | 🔴 pre-v1.0 |
| **Chunk 16** | World Standards 1: NTP sync, JSON logging, FK audit, graceful degradation + schema drift check script | ~4 hrs | 🟡 |
| **Chunk 17** | World Standards 2: Double-entry ledger, restore drills | ~4 hrs | 🟡 |
| **Chunk 18** | Auto Scheduled Backup **+ Google Drive sync + import** (rclone) | ~5-6 hrs | 🔴 HIGH |
| **Chunk 19** | Windows startup + update checker (GitHub releases) | ~3 hrs | 🟡 |
| **Chunk 20** | Auto error logging + crash report | ~2 hrs | 🟢 |
| **Chunk 22** | Hardware Testing 1 (power-cut, LAN 2-laptop) | ~4 hrs | 🔴 |
| **Chunk 23** | Hardware Testing 2 (ESC/POS printer, barcode scanner) | ~4 hrs | 🔴 |
| **Chunk 24** | Full Installer (PyInstaller + PostgreSQL + NSIS) — MUST rebuild dist at install | ~6 hrs | 🔴 |
| **Chunk 25** | Docs 1: Deploy + DR guide (Sinhala + English) | ~4 hrs | 🟡 |
| **Chunk 26** | Docs 2: User + admin manuals | ~4 hrs | 🟢 |

**Total remaining: ~35-45 hrs to v1.0.**

---

## 6. LOCKED DECISIONS (updated)

1-12. (from original — shop UUID, machine role, CLIENT auth, rate limits, full installer at end, PyInstaller collect-all, test DB safety, update checker via GitHub, recovery codes hashed, emergency reset localhost, 12 gates, test DB naming)
13. **`.ltbak` V2 format** (outer SHA-256 + Fernet) — V1 read preserved
14. **PITR restore manual PowerShell** — UI never auto-executes
15. **Test cluster 5433 manual `pg_ctl`** — not Windows service
16. **H7 (LAN HTTP)** accepted risk with `LTPOS_TRUST_LAN` env flag
17. **opencode + DeepSeek V3/V4 = worker tool** (DeepSeek default; Gemini free tier rate limits = unreliable)
18. **Worker = code only; tests via separate test chat (DeepSeek new chat)** — smoke by manager
19. **Customer on sale = optional** (Walk-in default), phone primary, both-empty rejected
20. **Buy cost = admin-only** (cashier completely hidden), admin review queue for cashier-created
21. **Image upload = OPTIONAL per item** (placeholder fallback: category color + initial)
22. **Image storage = filesystem** at `C:\ProgramData\LovelyTechPOS\item_images\`
23. **Image backup = 3B-4b-backup** — `.ltbak V3` includes images tar (MUST merge with 3B-4b)
24. **Frontend dist rebuild after each frontend session** — stale dist = false negative smoke
25. **Low stock threshold consume in inventory grid = 3D** (3B-4b stores, 3D displays)

---

## 7. 12 QUALITY GATES (MANDATORY — verbatim every worker prompt)

G1 validation | G2 client+server sync | G3 modal safety | G4 loading state | G5 error handling | G6 idempotent migrations | G7 atomic ops | G8 audit log | G9 edge cases | G10 real browser | G11 cross-theme | G12 regression

---

## 8. WORKER PROMPT STRUCTURE (every session)

1. ROLE — "Real business software. Quality > speed."
2. CONTEXT — branch, HEAD, system status
3. IN-SCOPE FILES (explicit list)
4. SCOPE — fix-by-fix or phase-by-phase
5. 12 QUALITY GATES (verbatim)
6. RULES (no shortcuts, no packages, style, budget)
7. INVESTIGATION FIRST for complex fixes
8. OUTPUT FORMAT — code only + completion report
9. SPLIT RULE — if ~75% used, stop at natural boundary
10. PRODUCTION SAFETY (read-only only)

---

## 9. KNOWN DEFERRALS / TECH DEBT

- WAL retention policy (Chunk 16)
- Base backup scheduled cadence (Chunk 16)
- Quarterly restore drill (Chunk 16)
- Defender pgdata monitor (defer)
- Multi-base-backup selector in PITR dialog (Chunk 16)
- Admin reauth query string → body migration (Chunk 16 or 3C)
- Schema drift detection script (Chunk 16) — from emergency fix
- `GET /items/admin-list` 200-row cap (pagination — future)
- Soft-deleted item reactivate UI (3D)
- Category manager placement move (3D)
- Item type code auto-handle (3D)
- Low stock threshold grid display (3D)
- Test users cleanup (script ready `scripts/cleanup_test_users.py`, not run)
- Item image backup (3B-4b-backup)
- Migration drift (test15 + prod — fixed emergency; prevent via schema check script Chunk 16)

---

## 10. NEXT IMMEDIATE ACTION

1. **Merge `fixes-3b4c` → main** (verified by smoke, dist rebuilt)
2. **Branch `image-upload-3b4b` from main**
3. **3B-4b prompt (image upload)** — DeepSeek V4.1, ~3 hrs
4. **3B-4b-backup prompt (V3 backup)** — same branch, ~2-3 hrs
5. **Combined smoke + test chat**
6. **Merge 3B-4b + 3B-4b-backup together** (must be together)
7. **3C → 3D → Chunk 16-26**

---

## 11. RESUME INSTRUCTIONS — New Manager Chat

If this chat hits limit:
1. Open new chat
2. Paste THIS file
3. Say: "I'm continuing Lovely Tech POS. Last: 3B-4c about to merge. Next: 3B-4b image upload + 3B-4b-backup V3 backup. Confirm image backup Option B (V3 tar in Fernet) before starting."
4. New manager will have full context

**Worker tool:** opencode + DeepSeek V3/V4. Branch strategy in Section 3. Deferred items in Section 9.

---

## 12. VERSION HISTORY

- v0.5.0 — Phase 2 DR (Chunks 1-15b)
- v0.6.0 — Security hardening + UI overhaul (Sessions 1A→3B-5) ← **current**
- v0.7.0 (target) — Image + backup V3 + audit mediums + polish (3B-4b→3D)
- v1.0.0 (target) — Chunks 16-26 complete, installer + docs

END OF PROJECT STATE