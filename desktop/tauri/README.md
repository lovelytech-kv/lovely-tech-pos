# Lovely Tech POS — Tauri 2 Windows Client

This is the Windows desktop shell. The frontend is built from `frontend/dist` and talks to the FastAPI server over the configured LAN API base URL.

Build prerequisites on the Windows development laptop: Rust stable, Tauri CLI, and WebView2. The cashier laptop does not need the development toolchain; it only hosts PostgreSQL + FastAPI.
