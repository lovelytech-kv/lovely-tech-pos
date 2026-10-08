"""Focused tests for durable server identity, mDNS advertisement, and discovery endpoint."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import app.core.config as config
import app.core.instance as instance_module
from app.main import app
from app.core.instance import load_instance_identity, get_instance_id, get_branch_code
from app.core.mdns import get_advertised_txt, start_mdns_advertisement, stop_mdns_advertisement


def _write_identity(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "instance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_instance_identity_is_persistent_across_loads(tmp_path, monkeypatch):
    """Repeated initialization returns the same instance_id."""
    identity_path = _write_identity(tmp_path, {"instance_id": "11111111-2222-3333-4444-555555555555"})
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))

    first = load_instance_identity()
    second = load_instance_identity()

    assert first["instance_id"] == "11111111-2222-3333-4444-555555555555"
    assert second["instance_id"] == first["instance_id"]
    assert get_instance_id() == first["instance_id"]


def test_instance_identity_generates_once_when_missing(tmp_path, monkeypatch):
    """A missing identity file is generated once and reused on subsequent loads."""
    identity_path = tmp_path / "instance.json"
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))

    first = load_instance_identity()
    assert identity_path.exists()

    second = load_instance_identity()

    assert first["instance_id"] == second["instance_id"]
    assert identity_path.read_text(encoding="utf-8") == json.dumps(first, indent=2)


def test_instance_identity_is_a_uuid(tmp_path, monkeypatch):
    """Generated identity is a valid UUID."""
    identity_path = tmp_path / "instance.json"
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))

    identity = load_instance_identity()
    parsed = uuid.UUID(identity["instance_id"])
    assert str(parsed) == identity["instance_id"]


def test_discovery_info_exposes_identity_and_no_secrets(tmp_path, monkeypatch):
    """GET /discovery/info returns only non-sensitive identity/protocol info."""
    identity_path = _write_identity(tmp_path, {"instance_id": "abcdef01-2345-6789-abcd-ef0123456789"})
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))

    client = TestClient(app)
    response = client.get("/discovery/info")

    assert response.status_code == 200
    body = response.json()

    assert body["product"] == "Lovely Tech POS System"
    assert body["protocol_version"] == "1.0.0"
    assert body["api_version"] == "1"
    assert body["instance_id"] == "abcdef01-2345-6789-abcd-ef0123456789"
    assert body["branch_code"] == "MAIN"

    forbidden = {"database_url", "secret_key", "backup_root", "database", "password", "token", "credentials"}
    for key in forbidden:
        assert key not in body, f"Sensitive key leaked: {key}"


def test_discovery_info_uses_branch_code_from_identity(tmp_path, monkeypatch):
    """Branch code from identity file takes precedence over settings."""
    identity_path = _write_identity(tmp_path, {"instance_id": "12345678-1234-1234-1234-123456789abc", "branch_code": "SHOP-A"})
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))
    monkeypatch.setattr(config.settings, "branch_code", "SHOULD-NOT-APPEAR")

    client = TestClient(app)
    response = client.get("/discovery/info")
    assert response.status_code == 200
    assert response.json()["branch_code"] == "SHOP-A"


def test_discovery_info_uses_settings_branch_code_when_identity_missing(tmp_path, monkeypatch):
    """When identity file has no branch_code, fall back to settings."""
    identity_path = _write_identity(tmp_path, {"instance_id": "12345678-1234-1234-1234-123456789abc"})
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))
    monkeypatch.setattr(config.settings, "branch_code", "FALLBACK")

    client = TestClient(app)
    response = client.get("/discovery/info")
    assert response.status_code == 200
    assert response.json()["branch_code"] == "FALLBACK"


def test_discovery_route_is_registered():
    """Ensure /discovery/info is reachable through the FastAPI application."""
    client = TestClient(app)
    response = client.get("/discovery/info")
    assert response.status_code == 200
    assert "instance_id" in response.json()


def test_mdns_txt_record_matches_discovery_info(tmp_path, monkeypatch):
    """mDNS TXT record fields match /discovery/info exactly."""
    identity_path = _write_identity(tmp_path, {"instance_id": "abcdef01-2345-6789-abcd-ef0123456789", "branch_code": "SHOP-A"})
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))
    monkeypatch.setattr(config.settings, "api_port", 9443)

    txt = get_advertised_txt()

    assert txt["product"] == "Lovely Tech POS System"
    assert txt["protocol_version"] == "1.0.0"
    assert txt["api_version"] == "1"
    assert txt["app_version"] == "0.4.0"
    assert txt["instance_id"] == "abcdef01-2345-6789-abcd-ef0123456789"
    assert txt["branch_code"] == "SHOP-A"
    assert txt["port"] == "9443"


def test_mdns_uses_configured_api_port(tmp_path, monkeypatch):
    """mDNS advertisement uses settings.api_port, not a hardcoded value."""
    identity_path = _write_identity(tmp_path, {"instance_id": "12345678-1234-1234-1234-123456789abc"})
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))

    for port in (8000, 8080, 9443, 3000):
        monkeypatch.setattr(config.settings, "api_port", port)
        txt = get_advertised_txt()
        assert txt["port"] == str(port)


def test_mdns_start_stop_idempotent(monkeypatch):
    """start/stop_mdns_advertisement are idempotent and safe to call repeatedly."""
    with patch("app.core.mdns.Zeroconf") as mock_zc:
        mock_instance = MagicMock()
        mock_zc.return_value = mock_instance

        start_mdns_advertisement()
        start_mdns_advertisement()  # second call should be no-op
        assert mock_zc.call_count == 1
        assert mock_instance.register_service.call_count == 1

        stop_mdns_advertisement()
        stop_mdns_advertisement()  # second call should be no-op
        assert mock_instance.unregister_service.call_count == 1
        assert mock_instance.close.call_count == 1


def test_mdns_failure_does_not_crash(monkeypatch):
    """mDNS registration failure is logged but does not raise."""
    with patch("app.core.mdns.Zeroconf", side_effect=OSError("multicast unavailable")):
        # Should not raise
        start_mdns_advertisement()
        stop_mdns_advertisement()


def test_mdns_service_type_and_name():
    """Service type and name are as specified."""
    from app.core.mdns import _SERVICE_TYPE, _SERVER_NAME

    assert _SERVICE_TYPE == "_lovely-tech-pos._tcp.local."
    assert _SERVER_NAME == "Lovely Tech POS Server"


def test_mdns_no_secrets_in_txt_record(tmp_path, monkeypatch):
    """TXT record must not contain sensitive configuration."""
    identity_path = _write_identity(tmp_path, {"instance_id": "11111111-2222-3333-4444-555555555555"})
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))

    txt = get_advertised_txt()

    forbidden = {"database_url", "secret_key", "backup_root", "password", "token", "credentials", "database"}
    for key in forbidden:
        assert key not in txt, f"Sensitive key leaked in mDNS TXT: {key}"