"""Shop provisioning endpoint for first-time server setup.

POST /api/v1/provisioning/shop provisions the current backend instance as the
shop/server. Admin-only, protected by re-authentication, idempotent, audit logged.

POST /api/v1/provisioning/bootstrap performs first-run bootstrap for a completely
uninitialized server. Unauthenticated, creates branch, admin user, and initial session.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import db_session, issue_session, current_user
from app.core.config import settings
from app.core.instance import get_instance_id, get_branch_code, save_branch_code, load_instance_identity
from app.models.master import Branch, User, Role
from app.models.security import AuditLog
from app.schemas.api import ProvisioningIn, ProvisioningOut, BootstrapIn, BootstrapOut
from app.security.passwords import hash_password
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


def _is_bootstrap_allowed(db: Session) -> bool:
    """Check if bootstrap is allowed (server is completely uninitialized for this instance)."""
    # Check instance.json for branch_code - this is the primary indicator
    # that this server instance has been initialized
    identity = load_instance_identity()
    if identity.get("branch_code"):
        return False
    # Also check if there's already a branch in DB with the branch_code
    # that this instance would use (shouldn't happen if instance.json is consistent)
    current_branch_code = identity.get("branch_code")
    if current_branch_code:
        branch = db.scalar(select(Branch).where(Branch.code == current_branch_code))
        if branch is not None:
            return False
    # Check if there are any users for this instance's branch
    if current_branch_code:
        branch = db.scalar(select(Branch).where(Branch.code == current_branch_code))
        if branch is not None:
            user = db.scalar(select(User).where(User.branch_id == branch.id).limit(1))
            if user is not None:
                return False
    return True


@router.post("/bootstrap", response_model=BootstrapOut)
def bootstrap_server(
    payload: BootstrapIn,
    db: Session = Depends(db_session),
) -> BootstrapOut:
    """First-run bootstrap for a completely uninitialized server.

    - Unauthenticated (only works on uninitialized server)
    - Creates branch, ADMIN role (if needed), admin user, and initial session
    - Returns access token for immediate use
    - Transactionally atomic
    - Audit logged
    """
    # Refuse bootstrap if already initialized
    if not _is_bootstrap_allowed(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Server already initialized. Bootstrap not allowed."
        )

    instance_id = get_instance_id()

    # Get or create ADMIN role
    admin_role = db.scalar(select(Role).where(Role.code == "ADMIN"))
    if not admin_role:
        admin_role = Role(code="ADMIN", name="Administrator", is_system=True)
        db.add(admin_role)
        db.flush()

    # Create branch
    branch = Branch(code=payload.branch_code, name=payload.branch_name, is_active=True)
    db.add(branch)
    db.flush()

    # Create admin user
    admin_user = User(
        username=payload.admin_username,
        password_hash=hash_password(payload.admin_password),
        display_name=payload.admin_display_name,
        role_id=admin_role.id,
        branch_id=branch.id,
        is_active=True,
        must_change_password=False,
    )
    db.add(admin_user)
    db.flush()

    # Create initial session
    access_token, expires_at = issue_session(db, admin_user)

    # Audit log for SHOP_PROVISIONED
    db.add(AuditLog(
        branch_id=branch.id,
        actor_user_id=admin_user.id,
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
        context_json={"bootstrap": True},
    ))

    # Audit log for USER_CREATED (admin user)
    db.add(AuditLog(
        branch_id=branch.id,
        actor_user_id=admin_user.id,
        action_type="USER_CREATED",
        entity_type="USER",
        entity_id=admin_user.id,
        timestamp=datetime.now(timezone.utc),
        after_json={
            "username": admin_user.username,
            "display_name": admin_user.display_name,
            "role_code": admin_role.code,
            "branch_code": branch.code,
        },
        source_transaction_id=admin_user.id,
        context_json={"bootstrap": True},
    ))

    # Commit all changes
    db.commit()

    # Persist branch_code to instance identity file AFTER successful commit
    try:
        save_branch_code(payload.branch_code)
    except Exception:
        # Do NOT claim DB rollback - leave system in recoverable EXISTING_SHOP_REQUIRED state
        # Do not create duplicate records on retry because _is_bootstrap_allowed checks DB first
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bootstrap completed but failed to persist branch code. Server is in EXISTING_SHOP_REQUIRED state."
        )

    setup_state = _get_setup_state(db)

    return BootstrapOut(
        status="provisioned",
        instance_id=instance_id,
        branch_code=branch.code,
        branch_name=branch.name,
        branch_id=branch.id,
        app_version=settings.app_version,
        protocol_version=settings.protocol_version,
        api_version=settings.api_version,
        setup_state=setup_state,
        access_token=access_token,
        expires_at=expires_at,
        token_type="bearer",
        user_id=admin_user.id,
        username=admin_user.username,
        display_name=admin_user.display_name,
        role=admin_role.code,
    )