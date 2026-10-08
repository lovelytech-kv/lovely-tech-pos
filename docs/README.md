# Lovely Tech POS System

Production-oriented LAN POS foundation based on the locked v2.0 Requirements and Database/Technical Blueprint.

## Stack
- PostgreSQL 18
- Python 3.13
- FastAPI
- SQLAlchemy 2.x
- Alembic
- React + TypeScript
- Tauri 2

## Current milestone
Database foundation is implemented: UUID identity, branches, users/roles/permissions, master data, document counters, audit/history primitives, idempotency primitives, record versions, and password hashing.

## Run database
```bash
docker compose up -d postgres
```

## Run migrations
```bash
cd backend
alembic upgrade head
```

## Run backend
```bash
uvicorn app.main:app --reload
```


## Foundation v12 hardening
- Cashier split-payment POS UI (Cash/Card/Online) with exact total validation.
- Admin-verified cashier password reset with forced password change.
- One-time admin offline recovery remains available.
- Purchase cost correction API with lineage safety and audit trail.
- ESC/POS-style plain-text receipt and A5 warranty document templates.
- Backend test suite: 22 passing.

Live PostgreSQL, printer, Tauri, and two-laptop LAN verification still require the actual shop environment.

## Current development/deployment decision

The production server is intentionally planned for the **cashier laptop**, because it is normally powered on throughout business hours. The owner's laptop is the development/admin client and is not a required always-on server. The cashier Windows account remains a Standard User. See `docs/DEPLOYMENT_LAN.md`.

## Development snapshot notes
This snapshot continues the locked v25 architecture and requirements. It includes the v26 continuation hardening recorded in `docs/DEVELOPMENT_STATUS.md`. The source-of-truth PDFs remain in `docs/` and are not superseded by this status file.


## Production acceleration / Windows deployment
- Cashier server scripts: `scripts/windows/Start-LovelyTechServer.ps1`, `Install-LovelyTechServer.ps1`, `Configure-LovelyTechFirewall.ps1`, `Verify-LovelyTechServer.ps1`.
- Owner client build: `scripts/windows/Build-LovelyTechClient.ps1 -ServerUrl http://CASHIER-IP:8000`.
- Encrypted PostgreSQL backup/restore runners are under `scripts/`.
- See `docs/WINDOWS_LAN_DEPLOYMENT.md` and `docs/PRODUCTION_ACCEPTANCE_MATRIX.md`.
