from fastapi.testclient import TestClient
from app.main import app

def test_health():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_route_is_defined():
    routes={r.path for r in app.routes if hasattr(r, 'path')}
    assert "/health/readiness" in routes


def test_api_v1_health_alias_matches_root_health():
    # The frontend's checkServerHealth() calls `${API base}/health` = /api/v1/health.
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    a, b = client.get("/health"), client.get("/api/v1/health")
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
