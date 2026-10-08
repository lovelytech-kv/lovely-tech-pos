"""Public discovery endpoint.

GET /discovery/info returns only non-sensitive identity/protocol information.
"""
from fastapi import APIRouter, Depends

from app.api.deps import db_session
from app.core.config import settings
from app.core.instance import get_instance_id, get_branch_code
from app.api.routes.provisioning import _get_setup_state

router = APIRouter(tags=["discovery"])


@router.get("/discovery/info")
def discovery_info(db=Depends(db_session)) -> dict:
    return {
        "product": settings.app_name,
        "protocol_version": settings.protocol_version,
        "api_version": settings.api_version,
        "app_version": settings.app_version,
        "instance_id": get_instance_id(),
        "branch_code": get_branch_code(),
        "setup_state": _get_setup_state(db),
    }