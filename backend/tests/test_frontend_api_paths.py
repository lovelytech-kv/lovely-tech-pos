"""Contract: every API path literal the frontend calls must exist on the FastAPI server.

Regression: DayEnd/Repair/approval screens called ``/operations/...`` which the backend never
served, so Day Start/End, Reload, Cash-in, Repair create/payment and approval review were all
HTTP 404 in the real UI even though every backend test passed.
"""
import re
from pathlib import Path

from app.main import app

SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"
PREFIX = "/api/v1"
# helper(<optional generic>)( <literal starting with "/"> ... ) -- api() plus the thin wrappers used in the UI.
CALL = re.compile(r"""\b(?:api|action|onAction|correct)(?:<[^>(]*>)?\(\s*([`'"])(/[^`'"]*?)\1""")


def _server_routes() -> list[list[str]]:
    # The OpenAPI schema is the authoritative flattened route table (app.routes may hold nested routers).
    routes = []
    for path in app.openapi()["paths"]:
        if path.startswith(PREFIX + "/"):
            routes.append(re.sub(r"\{[^}]+\}", "*", path[len(PREFIX):]).strip("/").split("/"))
    assert routes, "no /api/v1 routes found"
    return routes


def _matches(call: list[str], route: list[str]) -> bool:
    return len(call) == len(route) and all(a == b or a == "*" or b == "*" for a, b in zip(call, route))


def _frontend_calls() -> list[tuple[str, str]]:
    found = []
    for f in list(SRC.rglob("*.ts")) + list(SRC.rglob("*.tsx")):
        if ".test." in f.name:
            continue
        for m in CALL.finditer(f.read_text(encoding="utf-8")):
            path = re.sub(r"\$\{[^}]*\}", "*", m.group(2)).split("?")[0]
            found.append((f.relative_to(SRC).as_posix(), path))
    return found


def test_frontend_finds_api_calls_at_all():
    assert len(_frontend_calls()) > 40  # guards against the regex silently matching nothing


def test_every_frontend_api_path_exists_on_the_server():
    routes = _server_routes()
    missing = sorted({(f, p) for f, p in _frontend_calls()
                      if not any(_matches(p.strip("/").split("/"), r) for r in routes)})
    assert not missing, "Frontend calls endpoints the server does not serve:\n" + "\n".join(f"  {f}: {p}" for f, p in missing)
