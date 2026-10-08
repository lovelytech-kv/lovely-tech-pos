from fastapi.testclient import TestClient
from app.main import app

def test_health():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_route_is_defined():
    routes={r.path for r in app.routes if hasattr(r, 'path')}
    assert "/health/readiness" in routes
