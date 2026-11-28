# LOVELY TECH POS — MASTER PROJECT STATE

**Last Updated:** 2026-11-28 (after 3D-4 merge — UI phase COMPLETE)
**Version:** Backend 0.6.0 | Migration: `0049_receipt_options` (head)
**Status:** UI phase COMPLETE (Sessions 1A → 3D-4). Main = `4173dd7`. Next: Final Regression then Chunk 16 (World Standards).
**System NOT live** — shop using manual method. No real customer data. Production DB `lovely_tech_pos` = test data (352 users, mostly TEST_* prefixed).

---

## 1. PROJECT OVERVIEW

**Product:** Mobile phone repair shop POS. Offline-first, LAN, 1 server laptop + 1-3 client laptops on Windows (Tauri 2).
**Owner:** Lovely Tech (Sri Lanka).

**Stack:**
- Backend: FastAPI + Python 3.13 + PostgreSQL 18 + SQLAlchemy 2 + Alembic
- Frontend: React 19 + Vite 7.3.8 + Tailwind v4 + TS 5.9
- Desktop: Tauri 2

---

## 2. LOCATIONS

**Repo:** https://github.com/lovelytech-kv/lovely-tech-pos (main = `4173dd7`)
**Local:** `C:\lovely-tech-pos\`
**Docs:** `docs/PROJECT_STATE.md` (this file), `docs/audit-2026-11-17.md` (42 findings)
**Backups:** `C:\lovely-tech-pos-backups\` (chat exports, dumps), `C:\ProgramData\LovelyTechPOS\backups\` (.ltbak), `wal_archive\`, `pitr_base\`
**Test DB:** `lovely_tech_test15` (`.env` points here)
**Health:** `curl http://127.0.0.1:8000/api/v1/health`

---

## 3. GIT STATE

**main = `4173dd7`** — all UI work merged (Sessions 1A → 3D-4)
**Branches:**
- `main` (production)
- `security-session-1` (historical, merged)
- `purchases-redesign-3b5`, `deep-polish-3d4a`, `deep-polish-3d4b` (historical, merged)
- Various older branches (some unmerged experimental)

**Next branch (post-regression):** `chunk-16-standards`

---

## 4. COMPLETED SESSIONS (2 weeks of work, ~200 commits total)

### Security Hardening (Sessions 1A-1B-2-3A)
**29 audit fixes from 42-finding audit.** Commits: `efbf011` merge.
- 1A: C1 documents search, H1 login race, H3 logout scope, H4 absolute expiry, H5+H12+M19 password revoke, H6 session settings reauth, H11 recovery atomic, M18 code scope, M1 no session lock, M16 readable 422, L2 token strip
- 1B: H2 role reauth, H7 LTPOS_TRUST_LAN flag, H8 approval replay, H9 setup localhost+lock, H16+H18 XSS chain (escapeHtml + sessionStorage token), M7 APP_ENV validation
- 2: H10 FIFO race, H13 pg_restore engine dispose, H14 CLIENT fail-closed, H15 report export routing, H17 AbortSignal timeout, M8 manual server persist, M9 repair idempotency, M10 return idempotency, M12+M13 sales sequence guards, M14 identity timeout, M15 promise cache
- 3A: E6 reports auto-load, E11 returns search, E4 offline error, C6 cashier read-only, Receipt shop name+logo, E3 backup retry, E2 add item button

### Session 3B-1 — UI fixes (`acd3093`)
E2-nav Items tab label, Returns condition selector, Returns Enter key, Cashier Profit hidden, B1 lockout HTTP 423, D6 404 favicon, TEST_* cleanup script (not run)

### Session 3B-2 — POS Customer Flow (`b51bb40`)
CustomerPickerModal + quick-add, SalesTab customer strip, receipt customer line, history filter, auto-print line items, cashier admin options hidden

### Session 3B-3 — UI Foundation (`0d04c4b`)
Design tokens, collapsible sidebar (default collapsed, persisted), AppHeader with active tab name + 24h clock, receipt footer "Software by Lovely Tech · {phone}", header bug fix (`item.key` lookup)

### Session 3B-4 — Inventory Redesign (`3197fd5`)
Card grid (Square/Loyverse style), search/filter, grid/list toggle, modal form, header clock 12h. Emergency fix: purchases.payment_method schema drift (test15 + prod)

### Session 3B-5 series (40 commits, merged `9bcb269`)
**Purchases Redesign + Role Logic + CRUD:**
- Migration 0046: `items.buy_cost`, `items.needs_admin_review`, `items.low_stock_threshold`, partial index
- Qty bug fix, full line-entry redesign, history + detail, remove-line, quick-add supplier, item search
- Role buy cost (cashier hidden, admin visible), needs_admin_review flag, admin review queue
- Inline category/type creation, Categories/Types CRUD, Items soft-delete + reactivate
- Duplicate name blur check, history search by item, queue tiles promoted, widget renamed
- Smoke 8/8 PASS

### Session 3B-4c — Dead search removal (`1ca62e8`)
Removed dead header search input + Ctrl+K handler. 10 CSS locations cleaned.

### Session 3C-1 — Audit mediums (`df9686a`)
M2 audit log gaps, M3 N+1 queries (selectinload), M4+M21 FK indexes (migration 0047), M5 0035 placeholder documented, M11 todayLocal rollout (7 files), M17 recovery rate-limit query indexed

### Session 3C-2 + 3C-2a — Invoice Template Editor (`9f93f05`)
- Migration 0048: `invoice_templates` table (UUID PK, 12 toggles, partial unique index one-default-per-paper)
- 7 CRUD endpoints + audit, `GET /invoice-templates/default?paper_size=`
- Shared `receiptTemplate.ts` (deduplicated builders), locked footer enforced
- Full-screen editor modal (from 3D-1) with live preview iframe
- A5/A6 paper sizes
- 3C-2a: developer phone independent (`LTPOS_DEVELOPER_PHONE=0770290008`), clear Subtotal/TOTAL/Change labels, SKU formatting, normal (non-italic) footer

### Session 3D-1 — Receipt Enh + Popup Toast (`44b487a`)
- Migration 0049: `logo_monochrome`, `show_payment_method`, `show_cashier`, `show_customer_notes` (all default false)
- Canvas B&W logo helper + cache, SaleOut extended (payment_method_summary, cashier_name, customer_notes)
- Popup toast module (`popupToast.ts` — in-window rendering for 5 popup sites)
- Editor moved to full-screen modal (SettingsPanel compact card + manage button)
- A5/A6 paper CSS, editor toggles for new fields

### Session 3D-2 — Final UI Polish (`32a79c5`)
- CSS non-UTF-8 fix, Category Manager → Items workspace modal (admin-only)
- Item Type Code auto-handle (Advanced toggle), Reactivate soft-delete UI + endpoint
- Low stock threshold in grid chips (green/yellow/red per-item), editor field
- SVG sidebar icons (`NavIcon.tsx` — 18 stroke SVGs), sales screen polish (payment CSS fix, empty cart state, green Complete Sale, sticky Total Due footer), cross-tab token consistency

### Session 3D-3 — Modern Refinement (`fe56768`)
Glass-lite cards + layered shadows, accent glow on active nav icons, header clock accent pill + icon, micro-animations (fadeIn/modalEnter/targeted button lift, prefers-reduced-motion), sales sticky Total Due + Complete Sale footer, reactivate button ↻ icon + green tint, stock chip 2-line labeled tooltip

### Session 3D-4a-1 + 3D-4a-2 — Icon Family + Foundation (`93e2d66`)
- Icon.tsx with 80 `IconName` SVGs (stroke-based, currentColor, 18×18, fallback circle-question)
- 229 Icon instances across 38 files, 0 control glyphs remaining
- Button hierarchy: `.btn-primary/secondary/ghost/danger/success` + `.btn-sm/.btn-lg`
- Design tokens: `--font-sans`, `--leading-*`, `--text-2xs`, `--radius-full`, `--color-*-hover`
- Rollup 4.64.0 → 4.68.9 upgrade (tree-shaking restored, build 5.66s)

### Session 3D-4b-1 + 3D-4b-2 + 3D-4b-3 — Final Polish (`4173dd7`)
- `.data-table` + wrap/compact/interactive/wide + `.num`/`.actions` (7 tables migrated)
- Button specificity fix: `button.btn-*` scoping (0,1,1) beats legacy `.panel button` (0,1,1) by source order
- 15 hardcoded hover colors → tokens (light darkens accent, dark lightens)
- Header split date/time pills (time dominant 18px bold + accent glow)
- Theme toggle = **segmented 3-way (Light | Auto | Dark)** ← **LOCKED PREFERENCE**
- Icon glow: white halo on filled primary, accent glow on card edit/reactivate hover, modal close glow, empty state glow
- Cross-tab: 12 inconsistencies fixed (page gaps, card radius, typography, `.v0-main` padding)
- Legacy destructive → `.btn-danger` (13 migrated), inline ghost cancels → `.btn-ghost` (2), `.btn-sm` adoption (33 uses)
- World-standard pass (17 fixes: hardcoded cleanup, card radius tokens, no unwired handlers)
- Small fixes: modal close glow, Sales History filter active/inactive, Warranty button height, Stock gap+hierarchy, Backup/Restore Restore=danger

---

## 5. LOCKED DECISIONS (30 items — DO NOT CHANGE)

### Original (1-12)
1. Shop UUID never regenerates — persists through backup/restore
2. Machine role ≠ User role (SERVER/CLIENT ≠ ADMIN/CASHIER)
3. CLIENT never creates local admin (uses SERVER credentials)
4. Rate limit: 5/5min per IP on verify-admin, 5 fails/10min on /setup/* (shared bucket, reset on success)
5. Full installer at END (Chunk 24) — no rebuild waste
6. PyInstaller `--collect-all` FastAPI/Pydantic/SQLAlchemy
7. Test DB for destructive tests (`lovely_tech_test15`)
8. Update checker via GitHub releases (not own server)
9. Recovery codes hashed, shown once
10. Emergency reset localhost-only + `POS_EMERGENCY_KEY`
11. 12 Quality Gates apply to every chunk
12. Test DB for setup/CLIENT flows

### Additions (13-30)
13. **`.ltbak` V2** (outer SHA-256 + Fernet) — V1 read preserved forever
14. **PITR restore = manual PowerShell** — UI never auto-executes
15. **Test cluster 5433 manual `pg_ctl`** (not Windows service — port hijack risk)
16. **H7 (LAN HTTP)** accepted risk with `LTPOS_TRUST_LAN` env flag
17. **Worker tool = opencode + DeepSeek V3/V4.1** (DeepSeek default; Gemini free tier rate-limited = unreliable)
18. **Worker = code only; tests via separate Test chat (DeepSeek new chat)** — smoke by manager
19. **Customer on sale = optional** (Walk-in default), phone primary, both-empty rejected
20. **Buy cost = admin-only** (cashier completely hidden), admin review queue for cashier-created
21. **Image upload = DEFERRED post-v1.0** (not needed go-live)
22. **Item card display = category-color placeholder + initial** (no image)
23. **`.ltbak` V3 image backup = DEFERRED** (V2 current)
24. **Low stock threshold** (migration 0046) — grid display color chips + editor field
25. **Invoice templates = UUID PK** (not serial) — matches audit `entity_id`
26. **Locked footer = "Software by Lovely Tech · {LTPOS_DEVELOPER_PHONE}"** — env var default `0770290008`, no DB column, no API, no UI edit
27. **Theme toggle = segmented 3-way (Light | Auto | Dark)** — **permanent design base for mode selectors**
28. **Button hierarchy = `.btn-primary/secondary/ghost/danger/success` + `.btn-sm/.btn-lg`** — `button.btn-*` scoping beats legacy rules
29. **Icon family = `Icon.tsx` (80 SVG names)** — no Unicode/emoji in controls; `currentColor`, 18×18, stroke 1.75
30. **Rollup 4.68.9** — tree-shaking enabled (workaround removed after upgrade)
31. **Dev npm vulnerabilities (5)** — deferred to Chunk 24 (installer prep), production clean
32. **Frontend dist gitignored** — rebuild after frontend changes; Tauri installer (Chunk 24) rebuilds from latest source

---

## 6. 12 QUALITY GATES (MANDATORY)

G1 validation | G2 client+server sync | G3 modal safety | G4 loading state | G5 error handling | G6 idempotent migrations | G7 atomic ops | G8 audit log | G9 edge cases | G10 real browser | G11 cross-theme | G12 regression

---

## 7. WORKER WORKFLOW (locked)

**Tools:**
- **Code worker:** opencode + DeepSeek V3/V4.1 (`/model` → deepseek-v3 or v4). No Gemini (free tier rate limits = mid-session hangs).
- **Test worker:** separate DeepSeek new chat (test-only, no code changes).
- **Manager (you):** DeepSeek/Claude/ChatGPT chat — plan, prompts, review only.

**Per session:**
1. Manager writes worker prompt (12 gates + scope + split rule)
2. User pastes to fresh opencode chat (new chat per session — context limits)
3. Worker executes → commits each phase → completion report
4. Manager reviews report → approves OR sends fix prompt
5. Smoke test (manager-guided, user runs, 5-15 min)
6. Merge to main
7. Test chat (separate) after every 2-3 sessions

**Branch strategy:**
- New branch per session (`chunk-N-name`)
- Merge to main with `--no-ff` (explicit merge commit for audit trail)
- Push after every merge

---

## 8. TEST DBS / SAFETY

- **`lovely_tech_test15`** = primary test DB (`.env` points here)
- **`lovely_tech_test10`, `test11`, `test13`** = older test DBs (safe to drop when clean)
- **`lovely_tech_pos`** = "production" but actually test data (352 users, mostly TEST_*). **System not live** = safe to touch with care. Read-only verify only for safety.
- **PITR test cluster** = port 5433, `C:\LovelyTechTest\pgdata_pitr_test` (manual `pg_ctl`)
- **Test users** = 350 `TEST_*` prefixed — cleanup script ready at `scripts/cleanup_test_users.py` (not run yet)

---

## 9. AUDIT REFERENCE

`docs/audit-2026-11-17.md` = 42 verified findings (1C+18H+21M+4L, 1 FP rejected).

**All addressed:**
- 1A/1B/2/3A sessions = C1, H1-H18, M1, M7, M16, M18, M19, L2
- 3C-1 = M2, M3, M4, M5, M11, M17, M21
- Deferred to Chunk 16 or later (documented in Section 11)

---

## 10. NEXT IMMEDIATE ACTION — Final Regression

**~2 hrs, before Chunk 16. Manager-guided, user runs.**

### Full regression checklist:
1. **All 17 tabs load** — Dashboard, Sales, Sales History, Items, Customers, Repairs, Warranty, Stock, Purchases, Expenses, Cash/Day, Reports, Documents, Returns, Admin, Backup, Settings, Users
2. **Critical flows end-to-end:**
   - Sale: cart → customer pick → checkout → receipt auto-print → reprint (verify locked footer)
   - Purchase: supplier → line entry → save → admin cost entry → FIFO lot created
   - Return: search sale → return line → refund
   - Repair: create → parts → complete → finalize
   - Backup: create V2 → verify → restore (test15)
   - User: create → role change → password reset
3. **Audit re-check:** verify all 42 findings addressed or documented
4. **Production data intact:** `lovely_tech_pos`: 352 users, MAIN branch, shop_uuid `aad14246-...`
5. **Both themes:** light + dark all tabs
6. **Regression test failures:** `vitest --run` should be 90/92 (2 pre-existing failures `startup-discovery.test.tsx` — ThemeProvider mock, NOT caused by our work)

**After pass → Chunk 16.**

---

## 11. CHUNK 16-26 ROADMAP (detailed scope)

| Chunk | Scope | Est. |
|---|---|---|
| **16** | World Standards: NTP sync + JSON logging + FK audit + graceful degradation + **schema drift check script** (from emergency fix finding) | ~4 hrs |
| **17** | Double-entry ledger (Cash vs Profit) + restore drills | ~4 hrs |
| **18** | Auto scheduled backup (cron) + **Google Drive sync + import** (rclone) | ~5-6 hrs |
| **19** | Windows startup (autostart) + GitHub releases update checker | ~3 hrs |
| **20** | Auto error logging (frontend + backend) + crash report | ~2 hrs |
| **22** | Hardware testing 1: power-cut test, LAN 2-laptop concurrent test | ~4 hrs |
| **23** | Hardware testing 2: ESC/POS thermal printer + USB barcode scanner | ~4 hrs |
| **24** | Full installer: PyInstaller + PostgreSQL bundled + NSIS + **rebuild dist from latest source** + npm audit fix (dev vulns) | ~6 hrs |
| **25** | Documentation 1: Deployment + DR guide (Sinhala + English) | ~4 hrs |
| **26** | Documentation 2: User + admin manuals | ~4 hrs |
| **Total** | | **~40-45 hrs** |

**Deferred to post-v1.0:**
- Image upload + `.ltbak` V3 (image backup)
- mDNS auto-refresh on shop name change
- Multi-base-backup selector in PITR dialog
- WAL retention policy + base backup schedule
- Quarterly restore drill setup
- Defender pgdata monitor
- Admin reauth query-string → body migration
- Pagination for `GET /items/admin-list` (200-row cap)
- Full variant migration of remaining legacy buttons (purchases flow)

---

## 12. RESUME INSTRUCTIONS — New Manager Chat

**If this chat hits limit:**
1. Open new chat (DeepSeek/Claude/ChatGPT)
2. Paste THIS entire file + `docs/audit-2026-11-17.md`
3. Say: *"I'm continuing Lovely Tech POS. UI phase complete (Sessions 1A→3D-4, all merged to main `4173dd7`). Migration head `0049_receipt_options`. System NOT live. Next: Final Regression (~2 hrs) then Chunk 16 (World Standards). Worker tool = opencode + DeepSeek V3/V4.1. Test chat separate. Send me the Final Regression prompt first."*
4. New manager will have full context.

**For worker sessions:** Fresh opencode chat per session. Include full context (PROJECT_STATE + audit report + current branch/HEAD).

**For final regression:** Manager-guided (like smoke tests). User runs, manager verifies.

---

## 13. VERSION HISTORY

- v0.1.0 — Backend (Chunks 1-3)
- v0.2.0 — UI foundation (Chunks 4-6)
- v0.3.0 — Bug sweep + redesign (Chunks 7a-7c)
- v0.4.0 — Full feature set (Chunks 8-11)
- v0.5.0 — Phase 2 DR complete (Chunks 12-15b)
- **v0.6.0 — Security + UI overhaul complete (Sessions 1A → 3D-4)** ← **CURRENT**
- v0.7.0 (target) — Post-regression, deployment standards (Chunk 16-17)
- v1.0.0 (target) — Production ready (Chunk 24-26 done)

---

## 14. CRITICAL FACTS FOR NEW MANAGER

1. **System NOT live.** Shop uses manual method. No real customer data. Safe to touch production DB with care (but avoid destructive tests on it).
2. **Worker tool = opencode + DeepSeek V3/V4.1.** Not Gemini (rate limits). Not chat (context limits).
3. **Test chat = separate DeepSeek chat.** Code worker = code only. Test worker = tests only.
4. **Merge with `--no-ff`** + push immediately. **Never leave commits unpushed.**
5. **12 Quality Gates** in every worker prompt.
6. **Split rule:** if session hits 75% token budget, stop at natural boundary, partial report, continue in new chat.
7. **Real business software** — shop will use this daily for real money. Quality > speed.
8. **User's preferences locked:** theme toggle segmented 3-way, button hierarchy, glass cards + shadows, icon glow, customer optional, buy cost admin-only, locked footer.

END OF PROJECT STATE