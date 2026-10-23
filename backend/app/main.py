import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from psycopg import errors as psycopg_errors
from sqlalchemy.exc import DataError
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.router import api_router
from app.api.routes.discovery import router as discovery_router
from app.core.config import validate_production_settings
from app.backup.auto import run_pending_sync_once
from app.core.mdns import start_mdns_advertisement, stop_mdns_advertisement
from app.db.session import get_engine
from sqlalchemy import text

validate_production_settings()


async def _pending_backup_sync_loop() -> None:
    """Queued Google Drive upload: retry PENDING_SYNC backups until the network is back."""
    while True:
        await asyncio.sleep(max(30, settings.backup_sync_retry_interval_seconds))
        await asyncio.to_thread(run_pending_sync_once)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # zeroconf's synchronous register/unregister API must NOT run on the event-loop thread:
    # it raises EventLoopBlocked after a long timeout, so LAN discovery silently never worked
    # and startup stalled ~25s. Run it in a worker thread, in the background, so the API is
    # reachable immediately.
    mdns_task = asyncio.create_task(asyncio.to_thread(start_mdns_advertisement))
    sync_task = asyncio.create_task(_pending_backup_sync_loop()) if settings.google_drive_rclone_remote else None
    try:
        yield
    finally:
        if sync_task is not None:
            sync_task.cancel()
        try:
            await mdns_task
        except Exception:  # pragma: no cover - start_mdns_advertisement already logs failures
            pass
        await asyncio.to_thread(stop_mdns_advertisement)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# The desktop/Tauri client and the Vite development client are separate origins
# from the LAN FastAPI server. Keep the allow-list explicit; never use `*` for
# a credential-bearing POS API.
_cors_origins = [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


@app.exception_handler(DataError)
async def _invalid_identifier_handler(request: Request, exc: DataError):
    """A malformed id in the URL (e.g. /returns/abc) used to surface as HTTP 500; it is simply 'not found'."""
    if isinstance(getattr(exc, "orig", None), psycopg_errors.InvalidTextRepresentation):
        return JSONResponse(status_code=404, content={"detail": "Record not found (invalid identifier)"})
    raise exc


app.include_router(api_router)
app.include_router(discovery_router)

# The web/desktop client probes `${API base}/health` (i.e. /api/v1/health); /health stays for scripts.
@app.get("/api/v1/health", tags=["system"], include_in_schema=False)
@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "version": app.version}

@app.get("/health/readiness", tags=["system"])
def readiness() -> dict[str, str]:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")
    return {"status": "ready", "database": "ok", "version": app.version}
