"""Shop provisioning endpoint for first-time server setup.

POST /api/v1/provisioning/shop provisions the current backend instance as the
shop/server. Admin-only, protected by re-authentication, idempotent, audit logged.

POST /api/v1/provisioning/bootstrap performs first-run bootstrap for a completely
uninitialized server. Unauthenticated, creates branch, admin user, and initial session.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import func, inspect, literal, select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.api.deps import db_session, issue_session, current_user
from app.core.config import settings
from app.core.instance import get_instance_id, get_branch_code, save_branch_code, load_instance_identity
from app.core.shop_identity import (
    ShopIdentityError,
    ShopIdentityStatus,
    initialize_shop_identity,
    inspect_shop_identity,
)
from app.core.restore_state import (initialize_restore_state, acquire_restore_interlock, RestoreInterlockBusy, RestoreStateError, RestoreState)
from app.db.base import Base
from app.models.master import Branch, User, Role
from app.models.security import AuditLog
from app.schemas.api import ProvisioningIn, ProvisioningOut, BootstrapIn, BootstrapOut
from app.security.passwords import hash_password
from app.security.reauth import require_admin_reauth

router = APIRouter(prefix="/provisioning", tags=["provisioning"])

_BOOTSTRAP_LOCK_KEY = 0x4C54504F53
_BOOTSTRAP_SCHEMA_REVISION = "0036_import_batch_idempotency"
_BOOTSTRAP_REVISION_COLUMN_MIN_LENGTH = 64
_BOOTSTRAP_REQUIRED_COLUMNS = {
    "alembic_version": {"version_num"},
    "document_counters": {"prefix", "branch_id", "next_value"},
}


def _get_setup_state(db: Session) -> str:
    """Determine the current setup state for the frontend state machine."""
    shop_identity = inspect_shop_identity(db)
    if shop_identity.status in {
        ShopIdentityStatus.ENROLLMENT_REQUIRED,
        ShopIdentityStatus.INVALID,
    }:
        return "IDENTITY_ENROLLMENT_REQUIRED"
    if shop_identity.status is ShopIdentityStatus.EMPTY:
        return "NEW_SHOP_REQUIRED"

    # Check if branch exists in DB for the current instance's branch_code
    current_branch_code = get_branch_code()
    branch = db.scalar(select(Branch).where(Branch.code == current_branch_code))
    if branch is None:
        return "EXISTING_SHOP_REQUIRED"
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
    bind = db.get_bind()
    try:
        if bind.dialect.name == "postgresql":
            # Set isolation before any statement, then serialize workers and processes.
            db.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
            isolation_level = db.execute(text("SHOW transaction_isolation")).scalar_one()
            if isolation_level != "read committed":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Unsupported transaction isolation for bootstrap.",
                )
            db.execute(select(func.pg_advisory_xact_lock(_BOOTSTRAP_LOCK_KEY)))
        elif bind.dialect.name == "sqlite":
            app_env = (settings.app_env or "").strip().lower()
            if (
                app_env not in {"development", "test"}
                or not settings.sqlite_bootstrap_fallback_enabled
            ):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "SQLite bootstrap requires explicit test/development "
                        "fallback opt-in."
                    ),
                )
            # File-backed SQLite fallback; this is not the production lock contract.
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Bootstrap is unsupported for this database dialect.",
            )

        existing_tables = set(inspect(bind).get_table_names())
        required_tables = {
            table.name for table in Base.metadata.sorted_tables
        } | set(_BOOTSTRAP_REQUIRED_COLUMNS)
        required_columns = {
            table.name: {column.name for column in table.columns}
            for table in Base.metadata.sorted_tables
        }
        for table_name, columns in _BOOTSTRAP_REQUIRED_COLUMNS.items():
            required_columns.setdefault(table_name, set()).update(columns)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify database schema for bootstrap.",
        ) from exc

    missing_tables = required_tables - existing_tables
    if missing_tables:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database schema is incomplete. Bootstrap is not allowed.",
        )

    try:
        inspector = inspect(bind)
        missing_columns = {
            table_name: columns - {
                column["name"] for column in inspector.get_columns(table_name)
            }
            for table_name, columns in required_columns.items()
        }
        missing_columns = {
            table_name: columns
            for table_name, columns in missing_columns.items()
            if columns
        }
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database schema is incomplete. Bootstrap is not allowed.",
            )
        version_column = next(
            column
            for column in inspector.get_columns("alembic_version")
            if column["name"] == "version_num"
        )
        version_length = getattr(version_column["type"], "length", None)
        if (
            version_length is not None
            and version_length < _BOOTSTRAP_REVISION_COLUMN_MIN_LENGTH
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database schema is incomplete. Bootstrap is not allowed.",
            )
        revisions = db.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        if revisions != [_BOOTSTRAP_SCHEMA_REVISION]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unsupported database schema revision for bootstrap.",
            )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify database schema for bootstrap.",
        ) from exc

    # A missing external identity binding cannot establish that a restored DB is empty.
    # Static role/permission catalogs and migration metadata may be pre-seeded.
    setup_tables = {"roles", "permissions"}
    business_tables = [
        table for table in Base.metadata.sorted_tables if table.name not in setup_tables
    ]
    for table in business_tables:
        try:
            if db.execute(select(literal(1)).select_from(table).limit(1)).first():
                return False
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to verify database state for bootstrap.",
            ) from exc

    try:
        counters = db.execute(text("SELECT 1 FROM document_counters LIMIT 1")).first()
        if counters:
            return False
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify database state for bootstrap.",
        ) from exc

    try:
        identity = load_instance_identity()
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify server identity for bootstrap.",
        ) from exc
    if identity.get("branch_code"):
        return False
    return True


def _bootstrap_server_locked(
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
            detail=(
                "Server already initialized or existing shop state detected. "
                "Bootstrap not allowed."
            ),
        )

    try:
        restore_state = initialize_restore_state(settings.backup_root)
    except (OSError, RestoreStateError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Restore recovery state is unavailable; bootstrap is disabled.",
        ) from exc
    if restore_state.state is not RestoreState.READY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Restore recovery is incomplete; bootstrap is disabled.",
        )

    try:
        initialize_shop_identity(db)
    except ShopIdentityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Shop identity enrollment is required. Bootstrap is not allowed.",
        ) from exc

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

@router.post("/bootstrap", response_model=BootstrapOut)
def bootstrap_server(
    payload: BootstrapIn,
    db: Session = Depends(db_session),
) -> BootstrapOut:
    try:
        with acquire_restore_interlock(settings.backup_root, wait=True):
            return _bootstrap_server_locked(payload=payload, db=db)
    except RestoreInterlockBusy as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bootstrap or restore is already in progress.") from exc
    except RestoreStateError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Restore recovery state is unavailable; bootstrap is disabled.") from exc
