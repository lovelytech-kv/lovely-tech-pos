# LOVELY TECH POS — MASTER PROJECT STATE
**Last Updated:** 2026-11-13 (after Chunk 14c-1 mDNS + shop name fix)
**Version:** Backend 0.5.0 | Migrations: 0044_shop_name_backfill (head)
**Status:** Phase 2 in progress (14a+14b+14c-1 of ~26 chunks done)
---

## 1. PROJECT OVERVIEW

**Product:** Mobile phone repair shop POS system (offline-first, LAN, 2+ laptops)
**Business Scope:** Phone/accessory sales, repairs, warranty, inventory, purchases, returns
**Owner:** Lovely Tech (Sri Lanka)
**Deployment:** Tauri 2 desktop app (Windows), bundled installer planned

**Stack:**
- Backend: FastAPI + Python 3.13 + PostgreSQL 18 + SQLAlchemy 2 + Alembic
- Frontend: React 19 + Vite 7 + Tailwind v4 + TypeScript 5.9
- Desktop: Tauri 2 (Windows)
- Deploy target: 1 server laptop + 1-3 client laptops (LAN)

**Architecture:**
- Offline-first, no internet required
- Local backend per laptop (server + clients each run local backend)
- Server = source of truth, clients proxy to server
- Google Drive backup (optional, internet needed only for upload)

---

## 2. LOCATIONS

**Repo:** https://github.com/lovelytech-kv/lovely-tech-pos
**Local path:** C:\lovely-tech-pos\
- `backend/` — FastAPI
- `frontend/` — React + Vite
- `desktop/` — Tauri 2 wrapper
- `scripts/` — utility scripts
- `docs/` — documentation

**Backend env:** `C:\lovely-tech-pos\backend\.env`
**Database:** PostgreSQL 18, DB name `lovely_tech_pos`, user `lovely_pos`
**Backups:** `C:\lovely-tech-pos-backups\` (SQL dumps), `C:\ProgramData\LovelyTechPOS\backups\` (encrypted .ltbak)
**Logs:** `%LOCALAPPDATA%\LovelyTechPOS\logs\`

---

## 3. HOW TO RUN (DEV MODE)

**Backend (Terminal 1):**
```powershell
cd C:\lovely-tech-pos\backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
Frontend (Terminal 2):

powershell
cd C:\lovely-tech-pos\frontend
npm run dev
→ Opens at http://localhost:5173/

Tauri desktop (Terminal 3, optional):

powershell
cd C:\lovely-tech-pos\desktop
cargo tauri dev
Health check:

powershell
curl.exe http://127.0.0.1:8000/api/v1/health
4. COMPLETED CHUNKS (1-13)
#	Chunk	Status	Notes
1	CSS theme vars + performance mode	✅	styles.css foundation
2	Theme system (dark/light toggle)	✅	ThemeProvider.tsx
3	Navigation + permissions	✅	navigation.ts, permissions.ts
4	Home Dashboard	✅	HomeDashboard.tsx
5	Keyboard shortcuts	✅	F2/F4/Esc
6	Sales speed UX (auto-add)	✅	Smart search + recent items
7a	0035 migration bridge	✅	Fixed alembic chain
7b	Sales tab full redesign	✅	Two-column layout
7c	Cross-tab bug sweep	✅	Number inputs, toast, modals
8	Sales History + password security	✅	Backend GET /sales list
9a	Shop Profile + Logo	✅	branches table extended
9b	Accent picker + vendor + invoice prefix + docs	✅	Dual logo, permission-gated
9c	First-run Setup Wizard	✅	4-step (Welcome/Shop/Admin/Done)
10	User Management + session timeout	✅	Create/edit/deactivate users
11	Password Recovery	✅	8 recovery codes + emergency reset
12a	Shop Identity + Machine Role (backend)	✅	shop_identity, machine_identity tables
12b	Shop Identity + Machine Role (frontend)	✅	MachineSettings, SetupWizard Step 0
13	Client Join Authorization	✅	Rate-limited, no local admin
| 14a | Pre-Login Restore + Backup Import (backend) | ✅ | /setup/restore-from-file + /backup/import-file + migration 0043 |
| 14b | Frontend Restore Flow (RestoreFlow + Step 0.5) | ✅ | E2E verified on test10 — inspect → restore → login → dashboard |
| 14c-1 | mDNS Auto-Discovery + Reconnect + Shop Name Fix | ✅ | 3 root causes fixed: mDNS ServiceInfo addresses, shop_name write-path drift, CLIENT advertise collision. Migration 0044. T1-T8 + R1-R4 pass. 429 branches deactivated |
5. REMAINING ROADMAP (14-26)
#	Chunk	Scope	Time	Priority
14	Disaster Recovery + mDNS	Pre-login restore, backup import, mDNS discovery	3-4 days	🔴 CRITICAL
15	Backup Integrity + PITR	Corrupted backup validation, point-in-time recovery	2-3 hrs	🔴 HIGH
16	World Standards 1	NTP sync, JSON logging, FK audit	3 hrs	🟡 MED
17	World Standards 2	Double-entry ledger, restore drills	4 hrs	🟡 MED
18	Auto Scheduled Backup	Cron-based auto backup	2 hrs	🟡 MED
19	Windows Startup + Update Checker	Autostart, version check	3 hrs	🟡 MED
20	Auto Error Logging + Crash Report	Frontend + backend error capture	2 hrs	🟢 LOW
21	UI Polish (Design Tokens)	All tabs consistent styling	4 hrs	🟡 MED
22	Hardware Testing 1	Power-cut, LAN 2-laptop	4 hrs	🔴 HIGH
23	Hardware Testing 2	Printer, scanner	4 hrs	🔴 HIGH
24	Full Installer	PyInstaller + PostgreSQL bundled	6 hrs	🔴 HIGH
25	Documentation 1	Deploy + DR guide	4 hrs	🟡 MED
26	Documentation 2	User + admin manuals	4 hrs	🟢 LOW
Estimated total: ~55 hrs, 5-7 weeks

6. LOCKED DECISIONS (DO NOT CHANGE)
Shop UUID never regenerates — persists through backup/restore

Machine role ≠ User role — SERVER/CLIENT independent from ADMIN/CASHIER

CLIENT never creates local admin — uses SERVER credentials (Chunk 13)

Rate limit 5/5min per (IP, server_url) on verify-admin

No shortcut installer — full installer at end (Chunk 24)

PyInstaller with --collect-all for all FastAPI/Pydantic/SQLAlchemy deps

Test DB safety — never test on lovely_tech_pos (production)

Update checker via GitHub releases (not own server)

Recovery codes hashed — shown once only

Emergency reset localhost-only + POS_EMERGENCY_KEY

12 Quality Gates apply to every chunk (see section 9)

Test DB for setup/CLIENT flows — always use lovely_tech_test<N>

7. QUALITY GATES (MANDATORY — 12 GATES)
Every chunk MUST satisfy:

Required validation (char counter, inline error, disabled submit)

Client + Server sync (Pydantic min/max = frontend min/max)

Modal safety (confirm-on-discard, ESC guard)

Loading state (spinner, disabled, 30s timeout)

Error handling (try/catch, specific messages, retry)

Idempotent migrations (IF NOT EXISTS)

Atomic operations (single transaction, rollback)

Audit log (every state change)

Edge cases (empty, max, invalid, Unicode)

Real browser test (not just curl)

Cross-theme (light + dark)

Regression (existing features work)

These are non-negotiable. Worker bypass = chunk rejected.

8. CRITICAL FILE MAP
Backend entry: backend/app/main.py
Backend router: backend/app/api/router.py
Migrations: backend/alembic/versions/ (0001 → 0044)
Models: backend/app/models/master.py, shop_identity.py, machine_identity.py
Auth: backend/app/api/routes/auth.py
Setup: backend/app/api/routes/setup.py
Machine: backend/app/api/routes/machine.py
Sales: backend/app/api/routes/sales.py
Admin: backend/app/api/routes/admin.py

Frontend entry: frontend/src/main.tsx
Routing: frontend/src/features/pos/POSHome.tsx
API client: frontend/src/api/client.ts
Theme: frontend/src/theme/ThemeProvider.tsx
Permissions: frontend/src/config/permissions.ts
Navigation: frontend/src/config/navigation.ts
Shop context: frontend/src/features/settings/ShopContext.tsx
Sales: frontend/src/features/pos/POSHome.tsx (SalesTab inline)
Setup wizard: frontend/src/features/setup/SetupWizard.tsx
Machine settings: frontend/src/features/settings/MachineSettings.tsx

Design tokens: frontend/src/styles.css (last ~500 lines)

9. DATABASE STATE
Alembic head: 0043_backup_import
Production DB: lovely_tech_pos
Test DBs: lovely_tech_dev, lovely_tech_test_* (create as needed)

Key tables (50+):

users, roles, branches — auth

shop_identity — persistent shop UUID

machine_identity — SERVER/CLIENT role

items, categories, item_types — inventory master

purchases, purchase_lots, purchase_lines — purchases + FIFO

sales, sale_lines, payments — sales

repairs, repair_parts, repair_payments — repairs

returns, exchanges — returns

product_warranties, warranty_claims — warranty

audit_log, login_events — audit

backup_points, restore_events — backup

system_settings — config

password_reset_tokens — recovery

admin_recovery_codes — recovery codes

10. ENVIRONMENT
Required:

Windows 10/11

PostgreSQL 18 (C:\Program Files\PostgreSQL\18\bin)

Python 3.13 (backend)

Node 20+ (frontend)

Rust + Tauri 2 (desktop)

Key .env vars (backend/.env):

DATABASE_URL=postgresql+psycopg://lovely_pos:<pw>@127.0.0.1:5432/lovely_tech_pos

SECRET_KEY=<32+ chars random>

POS_EMERGENCY_KEY=<key for localhost admin reset>

CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,tauri://localhost,http://tauri.localhost

APP_ENV=development (dev) / production (deployed)

11. HOW TO RESUME — Manager Chat
If this chat hits limit or you need a fresh manager chat:

Open new chat with any AI (DeepSeek/Claude/ChatGPT)

Paste THIS ENTIRE FILE

Add: "I'm continuing the Lovely Tech POS project. Last completed: Chunk 13. Next: Chunk 14 (Disaster Recovery + mDNS). Send me the Chunk 14 prompt with 12 Quality Gates."

New manager will have full context.

12. HOW TO RESUME — Worker Chat (Chunk Execution)
For EVERY chunk, use NEW worker chat (avoid limit):

Open fresh chat

Paste this PROJECT_STATE.md

Paste the chunk prompt from manager

Add: "Execute this chunk. Follow all 12 quality gates. Do not skip tests. Report back with completion report in the exact format requested."

One chunk = one chat. No combining.

13. WORKER CHAT TEMPLATE (Paste First Line)
text
You are executing CHUNK N for the Lovely Tech POS project.

[PASTE PROJECT_STATE.md HERE]

[PASTE CHUNK N PROMPT HERE]
14. BACKUP STRATEGY
After every successful chunk:

git add . && git commit -m "Chunk N: <description>" && git push

pg_dump lovely_tech_pos > C:\lovely-tech-pos-backups\prod-YYYYMMDD-HHMM.sql

Update THIS file (PROJECT_STATE.md) — status table, migration head, new files

Save chat export (if possible)

Emergency rollback:

powershell
cd C:\lovely-tech-pos
git log --oneline -10  # find last good commit
git reset --hard <commit-hash>
# Restore DB from SQL dump if schema changed
15. KNOWN ISSUES / TECH DEBT
Rate limit in-memory — single-worker only. Redis needed for multi-process (future)

Admin reauth via query string — some endpoints use admin_password in URL (Phase 5 security audit)

GATE 11 (theme) — Chunk 13 CLIENT form not explicitly tested in dark mode

- ~~Test branches in DB — 430 branches~~ **FIXED in Chunk 14c-1**: 429 test branches deactivated (`is_active=false`), MAIN active. CSV snapshot: `C:\ProgramData\LovelyTechPOS\backups\branches-before-cleanup-*.csv`
- ~~shop_identity.shop_name NULL~~ **FIXED in Chunk 14c-1**: write-layer sync (`branch_profile.py`) + migration 0044 backfill + read fallback (`mdns.py`, `auto.py`)
- mDNS does not auto-refresh on shop name change — requires backend restart (deferred to Chunk 14c-2 / 15)

rclone optional — cloud backup requires rclone installed (bundle in Chunk 24)

shop_identity on CLIENT — currently shows "(client — see server)" — cosmetic

No multi-server support — single server per shop (by design, small shop focus)

16. CRITICAL SAFETY RULES
Never test on lovely_tech_pos (production) — use lovely_tech_test<N> DB

Always backup before migration — pg_dump production first

Restore .env after test — point back to production

Never commit .env — .gitignore protects it

Never commit node_modules — build from source

Test on real browser — not just curl

Test both themes — light + dark

Confirm every test manually — don't trust "assumed OK"

## 17. NEXT IMMEDIATE ACTION

**Chunk 14c-1 COMPLETE (2026-11-13)** — mDNS + shop name fix, E2E verified:
- 3 root causes: mDNS ServiceInfo missing addresses, shop_name write-path drift, CLIENT advertise collision
- 7 files fixed: mdns.py, main.py, machine.py, schemas/api.py, branch_profile.py, auto.py, migration 0044
- Frontend: discovery.ts (backend discovery), MachineSettings (Rediscover button)
- Tests: T1-T8 + R1-R4 pass
- Branch cleanup: 429 deactivated, 1 active (MAIN)
- Commit: 892b254 (pushed to GitHub)

**Chunk 14c-2** (next):
- mDNS auto-refresh on shop name change (no backend restart required)
- Google Drive import (cloud restore via rclone)
- Google Drive sync queue visible in UI

**Chunk 15** (after 14c-2):
- Backup integrity validation (corrupted backup detection)
- Point-in-time recovery (PITR)
- Rate limits on /setup/* endpoints


## 18. VERSION HISTORY

- v0.1.0 — Initial backend (Chunks 1-3)
- v0.2.0 — UI foundation (Chunks 4-6)
- v0.3.0 — Bug sweep + redesign (Chunks 7a-7c)
- v0.4.0 — Full feature set (Chunks 8-11)
- v0.5.0 (target) — Phase 2: Disaster recovery (Chunks 12-14) ← CURRENT
- v1.0.0 (target) — Production ready (Chunks 24-26)

END OF PROJECT STATE
Save this file. Update after every chunk. Never lose project context again.
