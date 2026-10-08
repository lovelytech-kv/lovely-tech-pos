"""mDNS service advertisement for LAN discovery."""

from __future__ import annotations

import logging
from typing import Any

from zeroconf import ServiceInfo, Zeroconf

from app.core.config import settings
from app.core.instance import get_instance_id, get_branch_code

logger = logging.getLogger(__name__)

_SERVICE_TYPE = "_lovely-tech-pos._tcp.local."
_SERVER_NAME = "Lovely Tech POS Server"

_zeroconf: Zeroconf | None = None
_service_info: ServiceInfo | None = None


def _build_txt_record() -> dict[str, str]:
    """Build TXT record matching /discovery/info identity."""
    return {
        "product": settings.app_name,
        "protocol_version": settings.protocol_version,
        "api_version": settings.api_version,
        "app_version": settings.app_version,
        "instance_id": get_instance_id(),
        "branch_code": get_branch_code(),
        "port": str(settings.api_port),
    }


def start_mdns_advertisement() -> None:
    """Register the mDNS service for LAN discovery.

    Safe to call multiple times; subsequent calls are no-ops.
    Failure is logged but does not raise.
    """
    global _zeroconf, _service_info

    if _service_info is not None:
        logger.debug("mDNS advertisement already active")
        return

    try:
        _zeroconf = Zeroconf()
        txt = _build_txt_record()
        _service_info = ServiceInfo(
            _SERVICE_TYPE,
            f"{_SERVER_NAME}.{_SERVICE_TYPE}",
            port=settings.api_port,
            properties=txt,
            server=f"{get_instance_id()[:8]}.local.",
        )
        _zeroconf.register_service(_service_info)
        logger.info(
            "mDNS advertisement registered: %s on port %d",
            _SERVICE_TYPE,
            settings.api_port,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("mDNS advertisement failed, continuing without LAN discovery: %s", exc)
        _cleanup()


def stop_mdns_advertisement() -> None:
    """Unregister the mDNS service and clean up resources.

    Safe to call multiple times; subsequent calls are no-ops.
    """
    global _zeroconf, _service_info

    if _service_info is None and _zeroconf is None:
        return

    try:
        if _service_info is not None:
            _zeroconf.unregister_service(_service_info)
            logger.info("mDNS advertisement unregistered")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("mDNS unregister failed: %s", exc)
    finally:
        _cleanup()


def _cleanup() -> None:
    global _zeroconf, _service_info
    try:
        if _zeroconf is not None:
            _zeroconf.close()
    except Exception:  # pragma: no cover - defensive
        pass
    _zeroconf = None
    _service_info = None


def get_advertised_txt() -> dict[str, str]:
    """Return the TXT record that would be advertised (for testing)."""
    return _build_txt_record()