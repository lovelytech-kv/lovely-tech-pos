"""mDNS service advertisement for LAN discovery."""
from __future__ import annotations

import logging
import socket
from typing import Any

from zeroconf import ServiceInfo, Zeroconf
from sqlalchemy import select

from app.core.config import settings
from app.core.instance import get_instance_id, get_branch_code

logger = logging.getLogger("uvicorn.error")

_SERVICE_TYPE = "_lovely-tech-pos._tcp.local."
_SERVER_NAME = "Lovely Tech POS Server"

_zeroconf: Zeroconf | None = None
_service_info: ServiceInfo | None = None


def _resolve_lan_ip() -> str | None:
    """Return the LAN IP this machine should advertise. None if only loopback available."""
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if not ip.startswith('127.'):
            return ip
    except (socket.gaierror, OSError):
        pass
    # Fallback: outbound route trick (works even when hostname -> 127.0.0.1)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        if ip and not ip.startswith('127.'):
            return ip
    except Exception:
        pass
    return None


def _load_shop_identity() -> tuple[str | None, str | None]:
    """Read shop_uuid + shop_name from DB. Fallback to branches.name when NULL.

    Defense-in-depth: old backups restored without shop_name, or installs
    predating Chunk 12a, will have shop_identity.shop_name = NULL while
    branches.name holds the real name. mDNS must never advertise NULL.
    """
    try:
        from app.db.session import get_session_factory
        from app.models.shop_identity import ShopIdentity
        from app.models.master import Branch
        db = get_session_factory()()
        try:
            shop = db.scalar(select(ShopIdentity).limit(1))
            shop_uuid = str(shop.shop_uuid) if shop else None
            shop_name = (shop.shop_name if shop else None) or None
            if not shop_name or not shop_name.strip():
                branch = db.scalar(select(Branch).order_by(Branch.created_at).limit(1))
                if branch and branch.name and branch.name.strip():
                    shop_name = branch.name.strip()
            return shop_uuid, shop_name
        finally:
            db.close()
    except Exception as exc:
        logger.debug("Could not load shop identity for mDNS TXT: %s", exc)
    return None, None

def _build_txt_record() -> dict[str, str]:
    """Build TXT record matching /discovery/info + shop identity."""
    shop_uuid, shop_name = _load_shop_identity()
    txt = {
        "product": settings.app_name,
        "protocol_version": settings.protocol_version,
        "api_version": settings.api_version,
        "app_version": settings.app_version,
        "instance_id": get_instance_id(),
        "branch_code": get_branch_code(),
        "port": str(settings.api_port),
    }
    if shop_uuid:
        txt["shop_uuid"] = shop_uuid
    if shop_name:
        txt["shop_name"] = shop_name
    return txt


def start_mdns_advertisement() -> None:
    """Register the mDNS service for LAN discovery.

    Idempotent. Failure is logged with type + message and never raised.
    """
    global _zeroconf, _service_info

    if _service_info is not None:
        logger.debug("mDNS advertisement already active")
        return

    lan_ip = _resolve_lan_ip()
    if not lan_ip:
        logger.warning(
            "mDNS advertisement skipped: no LAN IP available "
            "(only loopback reachable). Clients will fall back to manual URL."
        )
        return

    try:
        # Chunk 14c-1 followup: bind only the LAN IP, not the wildcard.
        # Chrome (and other mDNS apps) grab 0.0.0.0:5353 and intercept
        # multicast. Explicit interface binding lets Python coexist.
        try:
            _zeroconf = Zeroconf(interfaces=[lan_ip])
            logger.info("Zeroconf bound to explicit interface %s", lan_ip)
        except Exception as bind_exc:
            logger.warning(
                "Zeroconf explicit-interface bind failed (%s: %s); falling back to default",
                type(bind_exc).__name__, bind_exc,
            )
            _zeroconf = Zeroconf()

        txt = _build_txt_record()
        _service_info = ServiceInfo(
            _SERVICE_TYPE,
            f"{_SERVER_NAME}.{_SERVICE_TYPE}",
            port=settings.api_port,
            properties=txt,
            server=f"{get_instance_id()[:8]}.local.",
            addresses=[socket.inet_aton(lan_ip)],  # FIX: explicit LAN IP
        )
        _zeroconf.register_service(_service_info)
        logger.info(
            "mDNS advertisement registered: %s on %s:%d (shop_uuid=%s)",
            _SERVICE_TYPE, lan_ip, settings.api_port, txt.get("shop_uuid") or "n/a",
        )
    except Exception as exc:
        logger.warning(
            "mDNS advertisement failed (%s): %s",
            type(exc).__name__,
            str(exc) or "(no message)",
        )
        _cleanup()


def stop_mdns_advertisement() -> None:
    global _zeroconf, _service_info
    if _service_info is None and _zeroconf is None:
        return
    try:
        if _service_info is not None and _zeroconf is not None:
            _zeroconf.unregister_service(_service_info)
            logger.info("mDNS advertisement unregistered")
    except Exception as exc:
        logger.warning("mDNS unregister failed (%s): %s", type(exc).__name__, exc)
    finally:
        _cleanup()


def _cleanup() -> None:
    global _zeroconf, _service_info
    try:
        if _zeroconf is not None:
            _zeroconf.close()
    except Exception:
        pass
    _zeroconf = None
    _service_info = None


def get_advertised_txt() -> dict[str, str]:
    """Return the TXT record that would be advertised (for testing)."""
    return _build_txt_record()
