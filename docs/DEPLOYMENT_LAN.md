# Lovely Tech POS — LAN deployment model

## Locked production architecture

- **Cashier laptop** is the always-on LAN server during normal shop operation.
- **Owner laptop** is a client/development/admin machine and may be powered off without stopping POS service.
- Cashier uses a Windows **Standard User** account only; Windows Administrator credentials and PostgreSQL credentials are never exposed to the cashier.
- PostgreSQL is accessed only by FastAPI on the server laptop. Client laptops never connect directly to PostgreSQL.
- Core POS operation must continue over the local LAN without Internet.
- Google Drive is backup/recovery only, not live database synchronization.

## Development phase

For now, development is performed on the owner's laptop. Do not install the production POS stack on the cashier laptop until the application passes the local database, API, UI, and acceptance-test stages.

## PostgreSQL Windows installation

Stack Builder is optional for this project. Do **not** install PostGIS, pgAgent, ODBC/JDBC extras, replication packages, or unrelated Stack Builder packages merely because they are offered. The application uses PostgreSQL through Python's `psycopg` dependency.

Keep the PostgreSQL `postgres` password private. The cashier must never receive it.

## Final deployment sequence

1. Verify PostgreSQL service starts automatically with Windows.
2. Run Alembic migrations on the server laptop.
3. Bootstrap the branch, roles, permissions and first admin account securely.
4. Configure FastAPI to listen on the LAN interface on the server laptop.
5. Restrict the FastAPI port to the local/private network in Windows Firewall.
6. Verify owner laptop can connect over LAN while cashier laptop remains the database host.
7. Configure the POS desktop client to use the server's LAN address.
8. Configure thermal/A5 printers on the appropriate Windows machine(s).
9. Test POS with owner laptop powered off.
10. Test recovery after server laptop reboot, LAN interruption, printer failure, API timeout, duplicate submission, and backup interruption.

## Important production rule

A sale commits to the database before printing. A printer failure must never undo a completed sale. Reprint is a separate audited document event.
