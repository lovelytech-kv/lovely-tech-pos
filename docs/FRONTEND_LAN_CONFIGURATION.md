# Lovely Tech POS — Frontend LAN configuration

The desktop/client must call FastAPI on the cashier laptop. PostgreSQL is never exposed to the client.

## Development

Create `frontend/.env.local` from `.env.example` and set:

`VITE_API_BASE=http://<CASHIER-LAPTOP-IP>:8000/api/v1`

Use the server laptop's private LAN address, not a public address.

## Production

The packaged Tauri client should be built with the server LAN API base URL configured for the shop network. If the cashier laptop's IP changes, reserve a DHCP address in the router or update the client configuration before opening POS.

The client has a request timeout and clears the local session when FastAPI returns HTTP 401. A timeout does **not** automatically retry a financial transaction; transaction endpoints must continue using their existing idempotency keys.
