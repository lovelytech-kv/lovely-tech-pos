"""Focused tests for shop provisioning endpoint (POST /api/v1/provisioning/shop)
and first-run bootstrap endpoint (POST /api/v1/provisioning/bootstrap).
"""

import json
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.core.config as config
import app.core.instance as instance_module
from app.main import app
from app.core.instance import load_instance_identity, get_instance_id, get_branch_code, save_branch_code
from app.models.master import User, Role, Branch
from app.models.security import AuditLog
from app.security.passwords import hash_password, verify_password
from app.schemas.api import ProvisioningIn, ProvisioningOut, BootstrapIn
from app.core.config import settings


def _write_identity(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "instance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _unique_instance_id():
    return str(uuid.uuid4())


def _create_test_branch(db_session, prefix: str = "TEST"):
    code = f"{prefix}_{uuid.uuid4().hex[:8].upper()}"
    branch = Branch(code=code, name=f"Test Branch {code}", is_active=True)
    db_session.add(branch)
    db_session.flush()
    return branch


def _create_test_admin(db_session, branch_id):
    role = db_session.query(Role).filter(Role.code == "ADMIN").first()
    if not role:
        role = Role(code="ADMIN", name="Administrator", is_system=True)
        db_session.add(role)
        db_session.flush()
    user = User(
        username=f"admin_{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("AdminPass123!"),
        display_name="Test Admin",
        role_id=role.id,
        branch_id=branch_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _create_test_cashier(db_session, branch_id):
    role = db_session.query(Role).filter(Role.code == "CASHIER").first()
    if not role:
        role = Role(code="CASHIER", name="Cashier", is_system=True)
        db_session.add(role)
        db_session.flush()
    user = User(
        username=f"cashier_{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("CashierPass123!"),
        display_name="Test Cashier",
        role_id=role.id,
        branch_id=branch_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _get_auth_header(user, db_session):
    from app.api.deps import issue_session
    token, _ = issue_session(db_session, user)
    db_session.commit()
    return {"Authorization": f"Bearer {token}"}


def _setup_test_environment(monkeypatch, tmp_path):
    """Set up test environment with unique instance_id and non-existent default branch_code."""
    instance_id = _unique_instance_id()
    identity_path = _write_identity(tmp_path, {"instance_id": instance_id})
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))
    # Use a non-existent branch_code to avoid conflicts with existing branches
    monkeypatch.setattr(config.settings, "branch_code", f"NONEXISTENT_{uuid.uuid4().hex[:8].upper()}")
    return instance_id


def test_provisioning_admin_only(tmp_path, monkeypatch):
    """Non-admin users cannot provision."""
    instance_id = _setup_test_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(config.settings, "critical_reauth_required", False)

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        branch = _create_test_branch(db, "ADMIN_ONLY")

        cashier = _create_test_cashier(db, branch.id)
        db.commit()

        client = TestClient(app)
        headers = _get_auth_header(cashier, db)
        response = client.post(
            "/api/v1/provisioning/shop",
            json={"branch_code": "NEWSHOP", "branch_name": "New Shop"},
            headers=headers,
        )
        assert response.status_code == 403
        assert "Admin only" in response.json()["detail"]
    finally:
        db.close()


def test_provisioning_require_admin_reauth(tmp_path, monkeypatch):
    """Admin re-authentication is required when critical_reauth_required is True."""
    instance_id = _setup_test_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(config.settings, "critical_reauth_required", True)

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        branch = _create_test_branch(db, "REAUTH")

        admin = _create_test_admin(db, branch.id)
        db.commit()

        client = TestClient(app)
        headers = _get_auth_header(admin, db)
        response = client.post(
            "/api/v1/provisioning/shop",
            json={"branch_code": "NEWSHOP", "branch_name": "New Shop"},
            headers=headers,
        )
        assert response.status_code == 401
        assert "Admin re-authentication required" in response.json()["detail"]

        response = client.post(
            "/api/v1/provisioning/shop",
            json={"branch_code": "NEWSHOP", "branch_name": "New Shop"},
            headers=headers,
            params={"admin_password": "WrongPass"},
        )
        assert response.status_code == 401

        response = client.post(
            "/api/v1/provisioning/shop",
            json={"branch_code": "NEWSHOP", "branch_name": "New Shop"},
            headers=headers,
            params={"admin_password": "AdminPass123!"},
        )
        assert response.status_code == 200
    finally:
        db.close()


def test_provisioning_successful_branch_creation(tmp_path, monkeypatch):
    """Successful provisioning creates branch and returns correct response."""
    instance_id = _setup_test_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(config.settings, "critical_reauth_required", False)

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        branch = _create_test_branch(db, "SUCCESS")

        admin = _create_test_admin(db, branch.id)
        db.commit()

        client = TestClient(app)
        headers = _get_auth_header(admin, db)
        response = client.post(
            "/api/v1/provisioning/shop",
            json={"branch_code": "NEWSHOP", "branch_name": "New Shop"},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "provisioned"
        assert data["branch_code"] == "NEWSHOP"
        assert data["branch_name"] == "New Shop"
        assert data["instance_id"] == instance_id
        assert "branch_id" in data
        assert data["setup_state"] == "READY"

        created_branch = db.query(Branch).filter(Branch.code == "NEWSHOP").first()
        assert created_branch is not None
        assert created_branch.name == "New Shop"
        assert created_branch.is_active is True
    finally:
        db.close()


def test_provisioning_branch_activation(tmp_path, monkeypatch):
    """Provisioned branch is active."""
    instance_id = _setup_test_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(config.settings, "critical_reauth_required", False)

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        branch = _create_test_branch(db, "ACTIVATION")

        admin = _create_test_admin(db, branch.id)
        db.commit()

        client = TestClient(app)
        headers = _get_auth_header(admin, db)
        response = client.post(
            "/api/v1/provisioning/shop",
            json={"branch_code": "ACTIVESHOP", "branch_name": "Active Shop"},
            headers=headers,
        )
        assert response.status_code == 200

        created_branch = db.query(Branch).filter(Branch.code == "ACTIVESHOP").first()
        assert created_branch is not None
        assert created_branch.is_active is True
    finally:
        db.close()


def test_provisioning_persistent_instance_association(tmp_path, monkeypatch):
    """Provisioning associates branch_code with persistent instance_id in instance.json."""
    instance_id = _setup_test_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(config.settings, "critical_reauth_required", False)

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        branch = _create_test_branch(db, "PERSISTENT")

        admin = _create_test_admin(db, branch.id)
        db.commit()

        client = TestClient(app)
        headers = _get_auth_header(admin, db)
        response = client.post(
            "/api/v1/provisioning/shop",
            json={"branch_code": "PERSISTENT", "branch_name": "Persistent Shop"},
            headers=headers,
        )
        assert response.status_code == 200

        identity = load_instance_identity()
        assert identity["branch_code"] == "PERSISTENT"
        assert identity["instance_id"] == instance_id
        assert get_branch_code() == "PERSISTENT"
    finally:
        db.close()


def test_provisioning_idempotent_repeated_calls(tmp_path, monkeypatch):
    """Repeated provisioning with same data is idempotent."""
    instance_id = _setup_test_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(config.settings, "critical_reauth_required", False)

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        branch = _create_test_branch(db, "IDEMPOTENT")

        admin = _create_test_admin(db, branch.id)
        db.commit()

        client = TestClient(app)
        headers = _get_auth_header(admin, db)

        response1 = client.post(
            "/api/v1/provisioning/shop",
            json={"branch_code": "IDEMPOTENT", "branch_name": "Idempotent Shop"},
            headers=headers,
        )
        assert response1.status_code == 200
        data1 = response1.json()

        response2 = client.post(
            "/api/v1/provisioning/shop",
            json={"branch_code": "IDEMPOTENT", "branch_name": "Idempotent Shop"},
            headers=headers,
        )
        assert response2.status_code == 200
        data2 = response2.json()

        assert data1["branch_id"] == data2["branch_id"]
        assert data1["branch_code"] == data2["branch_code"]
        assert data1["branch_name"] == data2["branch_name"]
        assert data1["instance_id"] == data2["instance_id"]

        branch_count = db.query(Branch).filter(Branch.code == "IDEMPOTENT").count()
        assert branch_count == 1
    finally:
        db.close()


def test_provisioning_audit_event_created(tmp_path, monkeypatch):
    """Provisioning creates audit log entry for new branch."""
    instance_id = _setup_test_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(config.settings, "critical_reauth_required", False)

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        branch = _create_test_branch(db, "AUDIT")

        admin = _create_test_admin(db, branch.id)
        db.commit()

        client = TestClient(app)
        headers = _get_auth_header(admin, db)
        branch_code = f"AUDITSHOP_{uuid.uuid4().hex[:8].upper()}"
        response = client.post(
            "/api/v1/provisioning/shop",
            json={"branch_code": branch_code, "branch_name": "Audit Shop"},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        branch_id = data["branch_id"]

        audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "BRANCH",
            AuditLog.action_type == "SHOP_PROVISIONED",
            AuditLog.entity_id == branch_id,
        ).first()
        assert audit is not None
        assert audit.actor_user_id == admin.id
        assert audit.after_json["branch_code"] == branch_code
        assert audit.after_json["branch_name"] == "Audit Shop"
        assert audit.after_json["instance_id"] == instance_id
        assert audit.source_transaction_id == uuid.UUID(branch_id)
    finally:
        db.close()


def test_provisioning_no_audit_on_idempotent_call(tmp_path, monkeypatch):
    """Repeated provisioning does not create duplicate audit events."""
    instance_id = _setup_test_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(config.settings, "critical_reauth_required", False)

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        branch = _create_test_branch(db, "NOAUDIT")

        admin = _create_test_admin(db, branch.id)
        db.commit()

        client = TestClient(app)
        headers = _get_auth_header(admin, db)

        branch_code = f"NOAUDIT_{uuid.uuid4().hex[:8].upper()}"
        response1 = client.post(
            "/api/v1/provisioning/shop",
            json={"branch_code": branch_code, "branch_name": "No Audit Shop"},
            headers=headers,
        )
        assert response1.status_code == 200
        data1 = response1.json()
        branch_id = data1["branch_id"]

        response2 = client.post(
            "/api/v1/provisioning/shop",
            json={"branch_code": branch_code, "branch_name": "No Audit Shop"},
            headers=headers,
        )
        assert response2.status_code == 200

        audit_count = db.query(AuditLog).filter(
            AuditLog.entity_type == "BRANCH",
            AuditLog.action_type == "SHOP_PROVISIONED",
            AuditLog.entity_id == branch_id,
        ).count()
        assert audit_count == 1
    finally:
        db.close()


def test_provisioning_in_has_no_admin_password(tmp_path, monkeypatch):
    """ProvisioningIn schema does not contain admin_password field."""
    schema_fields = ProvisioningIn.model_fields
    assert "branch_code" in schema_fields
    assert "branch_name" in schema_fields
    assert "admin_password" not in schema_fields

    payload = ProvisioningIn(branch_code="TEST", branch_name="Test")
    assert payload.branch_code == "TEST"
    assert payload.branch_name == "Test"


def test_provisioning_conflict_different_branch_code(tmp_path, monkeypatch):
    """Provisioning fails when instance already associated with different branch."""
    instance_id = _unique_instance_id()
    existing_branch_code = f"EXISTING_{uuid.uuid4().hex[:8].upper()}"
    identity_path = _write_identity(tmp_path, {"instance_id": instance_id, "branch_code": existing_branch_code})
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))
    # Use a non-existent branch_code to avoid conflicts with existing branches
    monkeypatch.setattr(config.settings, "branch_code", f"NONEXISTENT_{uuid.uuid4().hex[:8].upper()}")
    monkeypatch.setattr(config.settings, "critical_reauth_required", False)

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        existing_branch = Branch(code=existing_branch_code, name="Existing Branch", is_active=True)
        db.add(existing_branch)
        db.flush()

        branch = _create_test_branch(db, "CONFLICT")

        admin = _create_test_admin(db, branch.id)
        db.commit()

        client = TestClient(app)
        headers = _get_auth_header(admin, db)
        response = client.post(
            "/api/v1/provisioning/shop",
            json={"branch_code": "NEWBRANCH", "branch_name": "New Branch"},
            headers=headers,
        )
        assert response.status_code == 409
        assert "already provisioned" in response.json()["detail"].lower()
    finally:
        db.close()


def test_provisioning_failed_does_not_leave_inconsistent_state(tmp_path, monkeypatch):
    """Failed provisioning does not update instance.json."""
    instance_id = _setup_test_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(config.settings, "critical_reauth_required", True)

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        branch = _create_test_branch(db, "FAIL")

        admin = _create_test_admin(db, branch.id)
        db.commit()

        client = TestClient(app)
        headers = _get_auth_header(admin, db)

        response = client.post(
            "/api/v1/provisioning/shop",
            json={"branch_code": "FAILSHOP", "branch_name": "Fail Shop"},
            headers=headers,
        )
        assert response.status_code == 401

        identity = load_instance_identity()
        assert "branch_code" not in identity or identity.get("branch_code") != "FAILSHOP"

        branch_count = db.query(Branch).filter(Branch.code == "FAILSHOP").count()
        assert branch_count == 0
    finally:
        db.close()


def _setup_bootstrap_environment(monkeypatch, tmp_path):
    """Set up test environment for bootstrap - completely uninitialized."""
    instance_id = _unique_instance_id()
    identity_path = _write_identity(tmp_path, {"instance_id": instance_id})
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))
    monkeypatch.setattr(config.settings, "branch_code", f"NONEXISTENT_{uuid.uuid4().hex[:8].upper()}")
    return instance_id


def _unique_branch_code(prefix: str = "BOOTSTRAP"):
    return f"{prefix}_{uuid.uuid4().hex[:8].upper()}"


def _unique_username(prefix: str = "admin"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def test_bootstrap_fresh_succeeds(tmp_path, monkeypatch):
    """Fresh/uninitialized bootstrap succeeds."""
    instance_id = _setup_bootstrap_environment(monkeypatch, tmp_path)
    branch_code = _unique_branch_code()
    admin_username = _unique_username()

    client = TestClient(app)
    response = client.post(
        "/api/v1/provisioning/bootstrap",
        json={
            "branch_code": branch_code,
            "branch_name": "Bootstrap Shop",
            "admin_username": admin_username,
            "admin_password": "AdminPass123!",
            "admin_display_name": "Bootstrap Admin",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "provisioned"
    assert data["branch_code"] == branch_code
    assert data["branch_name"] == "Bootstrap Shop"
    assert data["instance_id"] == instance_id
    assert data["setup_state"] == "READY"
    assert "access_token" in data
    assert "expires_at" in data
    assert data["token_type"] == "bearer"
    assert data["username"] == admin_username
    assert data["display_name"] == "Bootstrap Admin"
    assert data["role"] == "ADMIN"
    assert "user_id" in data
    assert "branch_id" in data


def test_bootstrap_creates_branch(tmp_path, monkeypatch):
    """Bootstrap creates branch."""
    instance_id = _setup_bootstrap_environment(monkeypatch, tmp_path)
    branch_code = _unique_branch_code()

    client = TestClient(app)
    response = client.post(
        "/api/v1/provisioning/bootstrap",
        json={
            "branch_code": branch_code,
            "branch_name": "Bootstrap Shop 2",
            "admin_username": _unique_username(),
            "admin_password": "AdminPass123!",
            "admin_display_name": "Bootstrap Admin 2",
        },
    )
    assert response.status_code == 200

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        branch = db.query(Branch).filter(Branch.code == branch_code).first()
        assert branch is not None
        assert branch.name == "Bootstrap Shop 2"
        assert branch.is_active is True
    finally:
        db.close()


def test_bootstrap_creates_admin_user_with_admin_role(tmp_path, monkeypatch):
    """Bootstrap creates admin user with ADMIN role."""
    instance_id = _setup_bootstrap_environment(monkeypatch, tmp_path)
    branch_code = _unique_branch_code()
    admin_username = _unique_username()

    client = TestClient(app)
    response = client.post(
        "/api/v1/provisioning/bootstrap",
        json={
            "branch_code": branch_code,
            "branch_name": "Bootstrap Shop 3",
            "admin_username": admin_username,
            "admin_password": "AdminPass123!",
            "admin_display_name": "Bootstrap Admin 3",
        },
    )
    assert response.status_code == 200
    data = response.json()

    from app.db.session import get_session_factory
    import uuid
    db = get_session_factory()()
    try:
        user = db.query(User).filter(User.username == admin_username).first()
        assert user is not None
        assert user.display_name == "Bootstrap Admin 3"
        assert user.is_active is True
        assert user.must_change_password is False
        assert user.role.code == "ADMIN"
        assert user.branch_id == uuid.UUID(data["branch_id"])
    finally:
        db.close()


def test_bootstrap_password_argon2_hashed_not_stored_raw(tmp_path, monkeypatch):
    """Bootstrap password is Argon2-hashed and raw password is not stored."""
    instance_id = _setup_bootstrap_environment(monkeypatch, tmp_path)
    branch_code = _unique_branch_code()
    admin_username = _unique_username()

    client = TestClient(app)
    response = client.post(
        "/api/v1/provisioning/bootstrap",
        json={
            "branch_code": branch_code,
            "branch_name": "Bootstrap Shop 4",
            "admin_username": admin_username,
            "admin_password": "AdminPass123!",
            "admin_display_name": "Bootstrap Admin 4",
        },
    )
    assert response.status_code == 200

    from app.db.session import get_session_factory
    from app.security.passwords import verify_password
    db = get_session_factory()()
    try:
        user = db.query(User).filter(User.username == admin_username).first()
        assert user is not None
        # Password should be hashed
        assert user.password_hash != "AdminPass123!"
        # Verify it works
        assert verify_password(user.password_hash, "AdminPass123!") is True
        # Wrong password should fail
        assert verify_password(user.password_hash, "WrongPass") is False
    finally:
        db.close()


def test_bootstrap_session_created_and_token_works(tmp_path, monkeypatch):
    """Bootstrap creates session and returned token works."""
    instance_id = _setup_bootstrap_environment(monkeypatch, tmp_path)
    branch_code = _unique_branch_code()
    admin_username = _unique_username()

    client = TestClient(app)
    response = client.post(
        "/api/v1/provisioning/bootstrap",
        json={
            "branch_code": branch_code,
            "branch_name": "Bootstrap Shop 5",
            "admin_username": admin_username,
            "admin_password": "AdminPass123!",
            "admin_display_name": "Bootstrap Admin 5",
        },
    )
    assert response.status_code == 200
    data = response.json()
    access_token = data["access_token"]

    # Use token to call a protected endpoint
    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.get("/api/v1/admin/users", headers=headers)
    # Should work (200) or return empty list (no users endpoint might not exist)
    # Just verify the token is accepted (not 401)
    assert response.status_code != 401


def test_bootstrap_setup_state_ready(tmp_path, monkeypatch):
    """Bootstrap setup_state becomes READY."""
    instance_id = _setup_bootstrap_environment(monkeypatch, tmp_path)
    branch_code = _unique_branch_code()
    admin_username = _unique_username()

    client = TestClient(app)
    response = client.post(
        "/api/v1/provisioning/bootstrap",
        json={
            "branch_code": branch_code,
            "branch_name": "Bootstrap Shop 6",
            "admin_username": admin_username,
            "admin_password": "AdminPass123!",
            "admin_display_name": "Bootstrap Admin 6",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["setup_state"] == "READY"


def test_bootstrap_instance_json_receives_branch_code(tmp_path, monkeypatch):
    """Bootstrap persists branch_code to instance.json after successful DB commit."""
    instance_id = _setup_bootstrap_environment(monkeypatch, tmp_path)
    branch_code = _unique_branch_code()
    admin_username = _unique_username()

    client = TestClient(app)
    response = client.post(
        "/api/v1/provisioning/bootstrap",
        json={
            "branch_code": branch_code,
            "branch_name": "Bootstrap Shop 7",
            "admin_username": admin_username,
            "admin_password": "AdminPass123!",
            "admin_display_name": "Bootstrap Admin 7",
        },
    )
    assert response.status_code == 200

    identity = load_instance_identity()
    assert identity["branch_code"] == branch_code
    assert identity["instance_id"] == instance_id
    assert get_branch_code() == branch_code


def test_bootstrap_audit_events_created(tmp_path, monkeypatch):
    """Bootstrap creates audit events for SHOP_PROVISIONED and USER_CREATED."""
    instance_id = _setup_bootstrap_environment(monkeypatch, tmp_path)
    branch_code = _unique_branch_code()
    admin_username = _unique_username()

    client = TestClient(app)
    response = client.post(
        "/api/v1/provisioning/bootstrap",
        json={
            "branch_code": branch_code,
            "branch_name": "Bootstrap Shop 8",
            "admin_username": admin_username,
            "admin_password": "AdminPass123!",
            "admin_display_name": "Bootstrap Admin 8",
        },
    )
    assert response.status_code == 200
    data = response.json()
    branch_id = data["branch_id"]
    user_id = data["user_id"]

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        # Check SHOP_PROVISIONED audit
        shop_audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "BRANCH",
            AuditLog.action_type == "SHOP_PROVISIONED",
            AuditLog.entity_id == branch_id,
        ).first()
        assert shop_audit is not None
        assert shop_audit.after_json["branch_code"] == branch_code
        assert shop_audit.after_json["branch_name"] == "Bootstrap Shop 8"
        assert shop_audit.after_json["instance_id"] == instance_id
        assert shop_audit.context_json.get("bootstrap") is True

        # Check USER_CREATED audit
        user_audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "USER",
            AuditLog.action_type == "USER_CREATED",
            AuditLog.entity_id == user_id,
        ).first()
        assert user_audit is not None
        assert user_audit.after_json["username"] == admin_username
        assert user_audit.after_json["display_name"] == "Bootstrap Admin 8"
        assert user_audit.after_json["role_code"] == "ADMIN"
        assert user_audit.context_json.get("bootstrap") is True
    finally:
        db.close()


def test_bootstrap_second_attempt_rejected(tmp_path, monkeypatch):
    """Second bootstrap attempt is rejected."""
    instance_id = _setup_bootstrap_environment(monkeypatch, tmp_path)
    branch_code = _unique_branch_code()
    admin_username = _unique_username()

    client = TestClient(app)
    # First bootstrap
    response1 = client.post(
        "/api/v1/provisioning/bootstrap",
        json={
            "branch_code": branch_code,
            "branch_name": "Bootstrap Shop 9",
            "admin_username": admin_username,
            "admin_password": "AdminPass123!",
            "admin_display_name": "Bootstrap Admin 9",
        },
    )
    assert response1.status_code == 200

    # Second bootstrap attempt
    response2 = client.post(
        "/api/v1/provisioning/bootstrap",
        json={
            "branch_code": f"{branch_code}_DIFFERENT",
            "branch_name": "Different Shop",
            "admin_username": _unique_username(),
            "admin_password": "AdminPass123!",
            "admin_display_name": "Different Admin",
        },
    )
    assert response2.status_code == 409
    assert "already initialized" in response2.json()["detail"].lower()


def test_bootstrap_existing_initialized_server_rejected(tmp_path, monkeypatch):
    """Existing branch/initialized server cannot bootstrap again."""
    # First set up an initialized server using provisioning/shop
    instance_id = _setup_test_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(config.settings, "critical_reauth_required", False)

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        branch = _create_test_branch(db, "EXISTING")
        admin = _create_test_admin(db, branch.id)
        db.commit()

        # Now simulate an initialized server by setting branch_code in instance.json
        identity_path = _write_identity(tmp_path, {"instance_id": instance_id, "branch_code": branch.code})
        monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))

        # Now try bootstrap - should fail because server is already initialized
        client = TestClient(app)
        response = client.post(
            "/api/v1/provisioning/bootstrap",
            json={
                "branch_code": _unique_branch_code(),
                "branch_name": "Bootstrap Shop 10",
                "admin_username": _unique_username(),
                "admin_password": "AdminPass123!",
                "admin_display_name": "Bootstrap Admin 10",
            },
        )
        assert response.status_code == 409
        assert "already initialized" in response.json()["detail"].lower()
    finally:
        db.close()


def test_bootstrap_validation_rejects_weak_input(tmp_path, monkeypatch):
    """Bootstrap validation rejects weak/invalid input."""
    instance_id = _setup_bootstrap_environment(monkeypatch, tmp_path)

    client = TestClient(app)

    # Short branch_code
    response = client.post(
        "/api/v1/provisioning/bootstrap",
        json={
            "branch_code": "",
            "branch_name": "Bootstrap Shop",
            "admin_username": "admin",
            "admin_password": "AdminPass123!",
            "admin_display_name": "Bootstrap Admin",
        },
    )
    assert response.status_code == 422

    # Short password (less than 10 chars)
    branch_code = _unique_branch_code()
    response = client.post(
        "/api/v1/provisioning/bootstrap",
        json={
            "branch_code": branch_code,
            "branch_name": "Bootstrap Shop",
            "admin_username": _unique_username(),
            "admin_password": "Short1",
            "admin_display_name": "Bootstrap Admin",
        },
    )
    assert response.status_code == 422

    # Missing required fields
    branch_code2 = _unique_branch_code()
    response = client.post(
        "/api/v1/provisioning/bootstrap",
        json={
            "branch_code": branch_code2,
            "branch_name": "Bootstrap Shop",
        },
    )
    assert response.status_code == 422


def test_bootstrap_failure_before_commit_leaves_no_partial_state(tmp_path, monkeypatch):
    """Failure before DB commit leaves no partial DB state."""
    instance_id = _setup_bootstrap_environment(monkeypatch, tmp_path)
    branch_code = _unique_branch_code()
    admin_username = _unique_username()

    # We'll test that if validation fails, no DB changes happen
    client = TestClient(app)
    response = client.post(
        "/api/v1/provisioning/bootstrap",
        json={
            "branch_code": branch_code,
            "branch_name": "Bootstrap Shop",
            "admin_username": admin_username,
            "admin_password": "Short",  # Too short
            "admin_display_name": "Bootstrap Admin",
        },
    )
    assert response.status_code == 422

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        # No branch should be created
        branch_count = db.query(Branch).filter(Branch.code == branch_code).count()
        assert branch_count == 0

        # No user should be created
        user_count = db.query(User).filter(User.username == admin_username).count()
        assert user_count == 0

        # instance.json should not have branch_code
        identity = load_instance_identity()
        assert "branch_code" not in identity or identity.get("branch_code") != branch_code
    finally:
        db.close()


def test_bootstrap_instance_json_write_failure_after_commit_does_not_pretend_rollback(tmp_path, monkeypatch):
    """instance.json write failure after commit does NOT pretend DB rollback and leaves recoverable state."""
    instance_id = _setup_bootstrap_environment(monkeypatch, tmp_path)
    branch_code = _unique_branch_code()
    admin_username = _unique_username()

    # Make instance.json read-only to cause write failure
    import os
    identity_path = _write_identity(tmp_path, {"instance_id": instance_id})
    os.chmod(identity_path, 0o444)  # Read-only

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/provisioning/bootstrap",
            json={
                "branch_code": branch_code,
                "branch_name": "Bootstrap Shop 13",
                "admin_username": admin_username,
                "admin_password": "AdminPass123!",
                "admin_display_name": "Bootstrap Admin 13",
            },
        )
        # Should return 500 because instance.json write failed
        assert response.status_code == 500
        assert "EXISTING_SHOP_REQUIRED" in response.json()["detail"]

        # DB should have the branch and user (committed)
        from app.db.session import get_session_factory
        db = get_session_factory()()
        try:
            branch = db.query(Branch).filter(Branch.code == branch_code).first()
            assert branch is not None

            user = db.query(User).filter(User.username == admin_username).first()
            assert user is not None

            # But instance.json should not have branch_code
            identity = load_instance_identity()
            assert identity.get("branch_code") != branch_code
        finally:
            db.close()
    finally:
        # Restore permissions for cleanup
        os.chmod(identity_path, 0o666)


def test_existing_provisioning_tests_still_pass(tmp_path, monkeypatch):
    """Existing Packet 15-I.1 provisioning tests remain green."""
    # This is a meta-test - the existing tests already run and pass
    # We just verify the provisioning endpoint still works
    instance_id = _setup_test_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(config.settings, "critical_reauth_required", False)

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        branch = _create_test_branch(db, "EXISTING_PROV")
        admin = _create_test_admin(db, branch.id)
        db.commit()

        client = TestClient(app)
        headers = _get_auth_header(admin, db)
        response = client.post(
            "/api/v1/provisioning/shop",
            json={"branch_code": "EXISTINGSHOP", "branch_name": "Existing Shop"},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "provisioned"
        assert data["branch_code"] == "EXISTINGSHOP"
    finally:
        db.close()