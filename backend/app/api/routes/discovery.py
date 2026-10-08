"""Public discovery endpoint.

GET /discovery/info returns only non-sensitive identity/protocol information.
"""
from fastapi import APIRouter

from app.core.config import settings
from app.core.instance import get_instance_id, get_branch_code

router = APIRouter(tags=["discovery"])


@router.get("/discovery/info")
def discovery_info() -> dict:
    return {
        "product": settings.app_name,
        "protocol_version": settings.protocol_version,
        "api_version": settings.api_version,
        "app_version": settings.app_version,
        "instance_id": get_instance_id(),
        "branch_code": get_branch_code(),
    }