# LOVELY TECH POS — MASTER PROJECT STATE

**Last Updated:** 2026-11-18 (after Audit — pre Security Session 1)
**Version:** Backend 0.5.0 | Migrations: 0045_pitr_base_backups (head)
**Status:** Phase 2 DR complete (Chunks 1-13, 14a-c-1, 15a, 15b done). Audit found 42 findings. Security Hardening Session 1/2/3 before Chunk 16.

---

## 1. PROJECT OVERVIEW

**Product:** Mobile phone repair shop POS system (offline-first, LAN, 2+ laptops)
**Owner:** Lovely Tech (Sri Lanka)
**Deployment:** Tauri 2 desktop app (Windows), bundled installer planned
**System status:** NOT LIVE — shop using manual method. No real customer data. Production DB = dev/test data (352 users, mostly TEST_* prefixed).

**Stack:**
- Backend: FastAPI + Python 3.13 + PostgreSQL 18 + SQLAlchemy 2 + Alembic
- Frontend: React 19 + Vite 7 + Tailwind v4 + TypeScript 5.9
- Desktop: Tauri 2 (Windows)

**Architecture:** offline-first, no internet required, server = source of truth, clients proxy to server. Google Drive backup optional (internet needed only for cloud upload). **Google Drive sync is NOT implemented yet — see Roadmap v2.**

---

## 2. LOCATIONS

**Repo:** https://github.com/lovelytech-kv/lovely-tech-pos
**Local path:** `C:\lovely-tech-pos\`
- `backend/` — FastAPI | `frontend/` — React+Vite | `desktop/` — Tauri 2 | `scripts/` — utilities | `docs/` — documentation
**Backend env:** `C:\lovely-tech-pos\backend\.env`
**DB:** PostgreSQL 18, `lovely_tech_pos` (prod/dev), user `lovely_pos`
**Backups:** `C:\lovely-tech-pos-backups\` (SQL dumps), `C:\ProgramData\LovelyTechPOS\backups\` (encrypted .ltbak), `C:\ProgramData\LovelyTechPOS\pitr_base\` (PITR base), `C:\ProgramData\LovelyTechPOS\wal_archive\` (WAL files)
**Logs:** `%LOCALAPPDATA%\LovelyTechPOS\logs\`

---

## 3. HOW TO RUN (DEV MODE)

**Backend:** `cd C:\lovely-tech-pos\backend` → `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
**Frontend:** `cd C:\lovely-tech-pos\frontend` → `npm run dev` → `http://localhost:5173/`
**Tauri:** `cd C:\lovely-tech-pos\desktop` → `cargo tauri dev`
**Health check:** `curl.exe http://127.0.0.1:8000/api/v1/health`

---

## 4. COMPLETED CHUNKS (1 → 15b)

| # | Chunk | Status | Notes |
|---|---|---|---|
| 1-6 | Foundation (theme, nav, dashboard, shortcuts, sales UX) | ✅ | |
| 7a-7c | Migration bridge, Sales redesign, bug sweep | ✅ | |
| 8 | Sales History + password security fix | ✅ | |
| 9a-9c | Shop Profile, Accent/vendor/invoice, Setup Wizard | ✅ | |
| 10 | User Management + session timeout | ✅ | |
| 11 | Password Recovery | ✅ | |
| 12a-12b | Shop Identity + Machine Role | ✅ | |
| 13 | Client Join Authorization | ✅ | Rate-limited |
| 14a | Pre-Login Restore + Backup Import (backend) | ✅ | Migration 0043 |
| 14b | Frontend Restore Flow | ✅ | |
| 14c-1 | mDNS + shop name fix | ✅ | Migration 0044 |
| 15a | Backup Integrity (V2 .ltbak, SHA-256, corrupted detection, /setup rate limit) | ✅ | Commit b9bb6d1 |
| 15b | PITR (WAL archiving, base backup, restore script, frontend dialog) | ✅ | Migration 0045, production WAL enabled 2026-11-16, base backup #1 taken |

**"Chunk 15c" does not exist** — 15a + 15b complete. "15c/16 handoff" in worker report was section naming only.

---

## 5. AUDIT (2026-11-17) — 42 VERIFIED FINDINGS

**Auditor:** Gemini Pro + ChatGPT + audit coordinator (static + manual verification)
**Limitation:** Static only. No runtime, no LAN stress test, no penetration test.

| Severity | Count |
|---|---|
| CRITICAL | 1 |
| HIGH | 18 |
| MEDIUM | 21 |
| LOW | 4 |
| **Total** | **42** (+ 1 FP rejected) |

**Critical combined risk:** H16 (JWT in localStorage) + H18 (unescaped receipt HTML) = live XSS → token theft → admin takeover. **Treat as CRITICAL pair, gate launch on fix.**

**Full findings:** See chat export `C:\lovely-tech-pos-backups\audit-2026-11-17.md` (paste the audit report).

### Manager decisions on 5 open questions:
1. **H16+H18 = COMBINED CRITICAL** — fix in Security Session 1.
2. **H7 (machine HTTP) = accepted risk** with `LTPOS_TRUST_LAN` env flag (default true, HTTPS-only when false). Small shop LAN is physically trusted.
3. **M20 (migration 0032 payment_method) = PENDING user confirmation.** Docstring says "Requirements 08" → likely intentional. Not in Session 1/2 scope.
4. **M5 (migration 0035 placeholder) = delete placeholder + document.** ImportMapping deferred to Phase 5.
5. **M7 (APP_ENV validation) = verify in Session 1.** Add startup hook if missing.

---

## 6. SECURITY HARDENING SESSIONS (pre-Chunk-16)

| Session | Scope | Est. | Status |
|---|---|---|---|
| **Session 1** | CRITICAL + HIGH security: C1, H1-H9, H11, H12, H16, H18, M1, M7, M16, M18, M19, L2 (19 fixes) | ~8-10 hrs | 🔴 NEXT — start now |
| **Session 2** | Data integrity + frontend routing: H10, H13, H14, H15, H17, M8, M9, M10, M12, M13, M14, M15 (~12 fixes) | ~7-9 hrs | 🔴 HIGH |
| **Session 3** | Medium + Chunk 21 UI Polish (merged): M2-M5, M11, M17, M20 (pending), M21, L1, L3, L4 + design tokens across all tabs | ~7-9 hrs | 🟡 MED |
| **Final regression** | Full tab walkthrough + audit re-check | ~2 hrs | 🔴 before v1.0 |

**Total ~24-30 hrs across 3-4 worker sessions.**

### Session 1 status (updated after completion):
- [ ] In progress — update this line when done

---

## 7. ROADMAP v2 (post-audit, updated)

| # | Chunk | Scope | Priority |
|---|---|---|---|
| **S1** | Security Session 1 | C1+H1-H9+H11+H12+H16+H18+M1+M7+M16+M18+M19+L2 | 🔴 HIGH |
| **S2** | Security Session 2 | H10, H13, H14, H15, H17, M8-M10, M12-M15 | 🔴 HIGH |
| **S3** | Security Session 3 = Chunk 21 merged | M2-M5, M11, M17, M20, M21, L1, L3, L4 + UI Polish | 🟡 MED (was LOW) |
| **16** | World Standards 1 | NTP sync, JSON logging, FK audit, graceful degradation | 🟡 MED |
| **17** | World Standards 2 | Double-entry ledger (Cash vs Profit), restore drills | 🟡 MED |
| **18** | Auto Scheduled Backup **+ Google Drive sync** | Cron backup + cloud upload + cloud import (Phase 5 deferral pulled forward) | 🔴 **HIGH** (was MED) |
| **19** | Windows Startup + Update Checker | Autostart, GitHub releases version check | 🟡 MED |
| **20** | Auto Error Logging + Crash Report | Frontend + backend capture | 🟢 LOW |
| **21** | **MERGED INTO SESSION 3** | UI Polish (design tokens) + audit mediums/lows | — |
| **22** | Hardware Testing 1 | Power-cut, LAN 2-laptop | 🔴 HIGH |
| **23** | Hardware Testing 2 | ESC/POS printer, barcode scanner | 🔴 HIGH |
| **24** | Full Installer (LAST) | PyInstaller + PostgreSQL + NSIS | 🔴 HIGH |
| **25** | Documentation 1 | Deploy + DR guide (Sinhala + English) | 🟡 MED |
| **26** | Documentation 2 | User + admin manuals | 🟢 LOW |

**Phase 5 cleanup** (post-v1.0): Admin reauth query-string→body (may move into Session 3), old test DB drops, discovery async refactor, GATE 11 screenshot formalization, WAL archive retention (16b), backup schedule (16b), multi-base-backup selector (16b), quarterly drill setup (16b), Defender pgdata monitor (16b).

---

## 8. WORKER TOOL — CHANGED 2026-11-18

**Old:** DeepSeek web chat (manual paste, context limits)
**New:** **opencode** (agentic terminal coder) + **DeepSeek API** ($5-10 topup)
**Reason:** DeepSeek web has new limits (Nov 2025). opencode has full disk access + terminal + no chat limit → 10x faster.

**Safety protocol for opencode:**
1. `git checkout -b <session-name>` before starting. Main branch protected.
2. Opencode prompt includes explicit in-scope / out-of-scope file list + "ask before modifying" rule.
3. Worker stops after each fix, shows diff, user confirms before next.
4. Tests one at a time; user runs in own terminal/browser, pastes output, confirms pass/fail.
5. Small commits per logical group; user reviews `git diff` before merge.
6. Session split: 5 hr limit per opencode session. Commit + review + restart opencode for next batch.

**Budget:** $5-10 per session ($2 too tight for 8-10 hr agentic work — re-reading files, retries, exploration).

---

## 9. 12 QUALITY GATES (MANDATORY — every chunk)

G1 validation | G2 client+server sync | G3 modal safety | G4 loading state | G5 error handling | G6 idempotent migrations | G7 atomic operations | G8 audit log | G9 edge cases | G10 real browser test | G11 cross-theme | G12 regression

Non-negotiable. Worker bypass = chunk rejected.

---

## 10. LOCKED DECISIONS (DO NOT CHANGE)

1. Shop UUID never regenerates — persists through backup/restore
2. Machine role ≠ User role — SERVER/CLIENT independent from ADMIN/CASHIER
3. CLIENT never creates local admin — uses SERVER credentials (Chunk 13)
4. Rate limit 5/5min per (IP, server_url) on verify-admin (Chunk 13); 5 failures/10min/IP on /setup/* (Chunk 15a, shared bucket, failure-counter, reset on success)
5. Full installer at END (Chunk 24)
6. PyInstaller `--collect-all` for FastAPI/Pydantic/SQLAlchemy deps
7. Test DB for all destructive tests (`lovely_tech_test<N>`)
8. Update checker via GitHub releases
9. Recovery codes hashed, shown once
10. Emergency reset localhost-only + `POS_EMERGENCY_KEY`
11. 12 Quality Gates every chunk
12. **`.ltbak` V2 format** (outer SHA-256 + Fernet payload) — V1 read path preserved forever
13. **PITR restore = manual elevated PowerShell.** UI never auto-executes.
14. **Test cluster 5433 = manual `pg_ctl`** (not Windows service — port hijack risk)
15. **Google Drive sync is NOT implemented** — pulled forward to Chunk 18. Phase 2 DR was "complete minus cloud offsite" — that label was misleading; now corrected in roadmap.
16. **H7 (machine HTTP) = accepted risk** with `LTPOS_TRUST_LAN` flag (small-shop LAN physically trusted)
17. **opencode + DeepSeek API = worker tool** (replaces DeepSeek web chat, Nov 2025 limits)

---

## 11. KNOWN DEFERRALS / TECH DEBT

**Pre-audit deferrals (still open):**
- Admin reauth via query string in some old endpoints (Phase 5 / may move to Session 3)
- 350 TEST_* users still in production (Phase 5 cleanup — or fold into Session 3 before installer)
- mDNS auto-refresh on shop name change needs backend restart (Phase 5)
- Multi-base-backup selector in PITR dialog (id=1 hardcoded — Chunk 16b)
- WAL archive retention policy (Chunk 16b)
- Base backup scheduled cadence (Chunk 16b)
- Quarterly restore drill setup (Chunk 16b)
- Defender pgdata monitor (deferred — monitor)
- Discovery endpoint async refactor (acceptable for small shop)
- Old backups pre-14b have null shop metadata (read fallback handles it)

**Post-audit items deferred to later sessions (see Section 6).**

**M20 pending user confirmation:** was migration 0032's removal of purchase `payment_method` intentional?

---

## 12. NEXT IMMEDIATE ACTION

**Security Session 1** (CRITICAL + HIGH, 19 fixes):
- C1 (documents/search 500)
- H1 (login race), H2 (update_user_role reauth), H3 (logout all sessions), H4 (sliding expiry), H5+H12+M19 (password reset sessions), H6 (session settings reauth), H7 (LAN trust flag), H8 (discount approval replay), H9 (setup localhost + race)
- H11 (recovery code race), H16+H18 (XSS chain — COMBINED CRITICAL)
- M1 (deps row lock), M7 (APP_ENV), M16 (422 toast), M18 (recovery code user scope)
- L2 (token in ltpos_user)

**Test DB:** `lovely_tech_test16` (fresh, migrations to 0045)
**Branch:** `security-session-1`
**Tool:** opencode + DeepSeek API
**Prompt:** Delivered 2026-11-18 in chat (Session 1 prompt with opencode-specific rules)

After Session 1: **Session 2 (Data Integrity)** — H10, H13, H14, H15, H17, M8-M10, M12-M15.

---

## 13. VERSION HISTORY

- v0.1.0 — Backend foundation (Chunks 1-3)
- v0.2.0 — UI foundation (Chunks 4-6)
- v0.3.0 — Bug sweep + redesign (Chunks 7a-7c)
- v0.4.0 — Full feature set (Chunks 8-11)
- v0.5.0 — Phase 2 DR complete (Chunks 12-15b) ← CURRENT
- v0.6.0 (target) — Post-audit security + UI polish (Sessions 1-3)
- v1.0.0 (target) — Production ready (Chunks 16-26 done)

---

## 14. RESUME NOTES

**If manager chat hits limit:** Paste this file + "I'm continuing Lovely Tech POS. Last: audit complete, Session 1 starting. Send Session 1 opencode prompt."

**If opencode/worker session hits issue:** New opencode session + "resume from branch `<name>` commit `<hash>`". Session 1 prompt has full context.

**If user returns after rest:** Current state = Section 12. Read Sections 5, 6, 7 for audit + roadmap.

END OF PROJECT STATE