# Lovely Tech POS documentation

This folder contains the current documentation set for Lovely Tech POS. The requirements PDF keeps its historical v2.0 filename but contains the reconciled requirements plus the deployment/recovery addendum; the database-blueprint PDF remains the v2.0 reference. The Markdown documents below are the maintained, implementation-aware project documentation.

## Canonical documents

- [Requirements](./REQUIREMENTS.md) — complete product and quality requirements.
- [Project status](./PROJECT_STATUS.md) — evidence-based implementation, validation, blockers, and cleanup record.
- [Architecture](./ARCHITECTURE.md) — component boundaries, data flow, security boundaries, and deployment model.
- [Operations and recovery](./OPERATIONS_AND_RECOVERY.md) — installation, setup, server/client operation, backup, restore, and troubleshooting.
- Deployment, discovery, and disaster recovery requirements and runbooks are documented in [Requirements](./REQUIREMENTS.md#14-deployment-server-discovery-and-disaster-recovery), [Architecture](./ARCHITECTURE.md#deployment-server-discovery-and-identity), and [Operations and recovery](./OPERATIONS_AND_RECOVERY.md#deployment-server-discovery-and-disaster-recovery).
- [Data import and migration](./DATA_IMPORT_AND_MIGRATION.md) — historical spreadsheet import requirements and controlled migration process.
- [Release checklist](./RELEASE_CHECKLIST.md) — required acceptance and release gates.

The dedicated deployment, zero-IP discovery, identity, upgrade, and disaster-recovery requirements are in [Requirements section 14](./REQUIREMENTS.md#14-deployment-server-discovery-and-disaster-recovery). Architecture and operator runbooks separately distinguish intended behavior from current implementation evidence.

## Source references

- [Final requirements (updated edition; canonical v2.0 filename)](./Lovely_Tech_POS_Final_Requirements_v2.0.pdf)
- [Database and technical blueprint v2.0](./Lovely_Tech_POS_Database_Technical_Blueprint_v2.0.pdf)
- Tauri component setup notes remain in [`desktop/tauri/README.md`](../desktop/tauri/README.md).

## Project overview

Lovely Tech POS is a LAN-oriented point-of-sale application. The intended production topology keeps PostgreSQL and the FastAPI service on the always-on Cashier laptop. Desktop clients communicate with the API over the LAN; client machines do not connect directly to PostgreSQL. Google Drive is optional backup/recovery storage, not live database synchronization.

The current workspace includes backend, frontend, Tauri desktop wrapper, Windows deployment scripts, database migrations, and automated tests. Their implementation and verification status are deliberately separated in [Project status](./PROJECT_STATUS.md). The software must not be described as production-ready until the physical, security, data, and operational gates in the [release checklist](./RELEASE_CHECKLIST.md) have passed.
