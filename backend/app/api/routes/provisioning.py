"""Shop provisioning endpoint for first-time server setup.

POST /api/v1/provisioning/shop provisions the current backend instance as the
shop/server. Admin-only, protected by re-authentication, idempotent, audit logged.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import db_session, current_user
from app.core.config import settings
from app.core.instance import get_instance_id, get_branch_code, save_branch_code
from app.models.master import Branch, User
from app.models.security import AuditLog
from app.schemas.api import ProvisioningIn, ProvisioningOut
from app.security.reauth import require_admin_reauth

router = APIRouter(prefix="/provisioning", tags=["provisioning"])


def _get_setup_state(db: Session) -> str:
    """Determine the current setup state for the frontend state machine."""
    # Check if branch exists in DB for the current instance's branch_code
    current_branch_code = get_branch_code()
    branch = db.scalar(select(Branch).where(Branch.code == current_branch_code))
    if branch is None:
        return "NEW_SHOP_REQUIRED"
    identity = __import__('app.core.instance', fromlist=['load_instance_identity']).load_instance_identity()
    if not identity.get("branch_code"):
        return "EXISTING_SHOP_REQUIRED"
    return "READY"


def _is_already_provisioned(db: Session, branch_code: str) -> Branch | None:
    """Check if branch exists and matches the current instance identity."""
    return db.scalar(select(Branch).where(Branch.code == branch_code))


@router.post("/shop", response_model=ProvisioningOut)
def provision_shop(
    payload: ProvisioningIn,
    admin_password: str | None = Query(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(db_session),
) -> ProvisioningOut:
    """Provision the current backend instance as the shop/server.

    - Admin only
    - Requires admin re-authentication (if critical_reauth_required)
    - Idempotent: safe to call multiple times with same data
    - Transactionally atomic (instance identity persisted after DB commit)
    - Audit logged
    - Tied to persistent instance_id
    """
    # Admin only
    if user.role.code.upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only"
        )

    # Admin re-authentication (for critical operations)
    require_admin_reauth(user=user, password=admin_password, db=db, action="shop provisioning")

    instance_id = get_instance_id()
    current_branch_code = get_branch_code()

    # Check if already provisioned with the requested branch code
    existing_branch = _is_already_provisioned(db, payload.branch_code)
    if existing_branch:
        # Idempotent: already provisioned correctly - verify instance identity matches
        if existing_branch.code != current_branch_code:
            # This should not happen if instance.json is consistent, but handle gracefully
            # Update instance.json to match DB (after commit)
            pass
        branch = existing_branch
        is_new_provisioning = False
    else:
        # Check if this server instance already has a different branch code in instance.json
        if current_branch_code and current_branch_code != payload.branch_code:
            # Server instance already associated with a different branch in instance.json
            existing_current_branch = db.scalar(select(Branch).where(Branch.code == current_branch_code))
            if existing_current_branch:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"This server instance is already provisioned for branch '{current_branch_code}'. Cannot provision a second shop identity without proper workflow."
                )
        # Create new branch
        branch = Branch(code=payload.branch_code, name=payload.branch_name, is_active=True)
        db.add(branch)
        db.flush()
        is_new_provisioning = True

    # Audit log - only for new provisioning to avoid duplicate "created" events
    if is_new_provisioning:
        db.add(AuditLog(
            branch_id=branch.id,
            actor_user_id=user.id,
            action_type="SHOP_PROVISIONED",
            entity_type="BRANCH",
            entity_id=branch.id,
            timestamp=datetime.now(timezone.utc),
            after_json={
                "branch_code": branch.code,
                "branch_name": branch.name,
                "instance_id": instance_id,
            },
            source_transaction_id=branch.id,
        ))

    db.commit()

    # Persist branch_code to instance identity file AFTER successful commit
    # This ensures atomicity: if DB commit fails, instance.json is not updated
    save_branch_code(payload.branch_code)

    setup_state = _get_setup_state(db)

    return ProvisioningOut(
        status="provisioned",
        instance_id=instance_id,
        branch_code=branch.code,
        branch_name=branch.name,
        branch_id=branch.id,
        app_version=settings.app_version,
        protocol_version=settings.protocol_version,
        api_version=settings.api_version,
        setup_state=setup_state,
    )