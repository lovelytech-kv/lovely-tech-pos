"""Durable file-based server instance identity.

A single stable UUID is generated once for a production server and stored
in a dedicated application-data directory outside the source tree. The UUID
does not regenerate on restart and contains no secrets.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


def _identity_path() -> Path:
    """Resolve the identity file path from settings (lazy import to avoid cycles)."""
    from app.core.config import settings
    return Path(settings.instance_id_file)


def _ensure_identity_directory() -> Path:
    path = _identity_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_instance_identity() -> dict[str, Any]:
    """Load the server identity from disk, generating it on first use.

    Returns a dict with at least ``instance_id`` and ``branch_code``.
    """
    path = _ensure_identity_directory()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("instance_id"):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    identity = {
        "instance_id": str(uuid.uuid4()),
    }
    path.write_text(json.dumps(identity, indent=2), encoding="utf-8")
    return identity


def get_instance_id() -> str:
    """Return the stable instance UUID, creating it if necessary."""
    return load_instance_identity()["instance_id"]


def get_branch_code() -> str:
    """Return the branch code associated with this server instance."""
    from app.core.config import settings
    identity = load_instance_identity()
    return identity.get("branch_code") or settings.branch_code


def save_branch_code(branch_code: str) -> None:
    """Persist the branch code to the instance identity file."""
    path = _ensure_identity_directory()
    identity = load_instance_identity()
    identity["branch_code"] = branch_code
    path.write_text(json.dumps(identity, indent=2), encoding="utf-8")