import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

import app.core.config as config
import app.api.routes.backup as backup_module
import app.main as main_module
from app.api.deps import db_session, issue_session, token_hash
from app.api.router import api_router
from app.api.routes.discovery import router as discovery_router
from app.core.shop_identity import ShopIdentityStatus, inspect_shop_identity
from app.core.restore_state import (
    RestoreState,
    restore_state_path,
    write_restore_state,
)
from app.db.session import Base
from app.main import health
from app.models.auth import UserSession
from app.models.master import Branch, Permission, Role, RolePermission, User
from app.models.sales import Customer
from app.models.shop_identity import ShopIdentity


@pytest.fixture
def identity_app(tmp_path, monkeypatch):
    database_path = tmp_path / "identity-write-gate.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE document_counters ("
            "prefix VARCHAR(20) NOT NULL, branch_id VARCHAR(36) NOT NULL, "
            "next_value BIGINT NOT NULL, PRIMARY KEY (prefix, branch_id))"
        )

    identity_file = tmp_path / "instance.json"
    identity_file.write_text(
        json.dumps({"instance_id": str(uuid.uuid4())}), encoding="utf-8"
    )
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_file))
    monkeypatch.setattr(config.settings, "backup_root", str(tmp_path / "backups"))
    write_restore_state(
        restore_state_path(tmp_path / "backups"),
        state=RestoreState.READY,
        phase="TEST_INITIALIZED",
    )
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def isolated_db_session():
        with session_factory() as db:
            yield db

    app = FastAPI()
    app.include_router(api_router)
    app.include_router(discovery_router)
    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route(
        "/health/readiness", main_module.readiness, methods=["GET"]
    )
    monkeypatch.setattr(main_module, "get_engine", lambda: engine)
    app.dependency_overrides[db_session] = isolated_db_session
    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()

    yield SimpleNamespace(
        app=app,
        engine=engine,
        session_factory=session_factory,
        identity_file=identity_file,
    )
    engine.dispose()


def _create_user(environment, *, role_code="ADMIN", permissions=(), expired=False):
    with environment.session_factory() as db:
        branch = Branch(code=f"BR-{uuid.uuid4().hex[:8]}", name="Test Branch")
        role = db.scalar(select(Role).where(Role.code == role_code))
        if role is None:
            role = Role(
                code=role_code,
                name=role_code.title(),
                is_system=role_code == "ADMIN",
            )
            db.add(role)
        db.add(branch)
        db.flush()
        user = User(
            username=f"{role_code.lower()}-{uuid.uuid4().hex[:8]}",
            password_hash="test-hash",
            display_name=role_code.title(),
            role=role,
            branch=branch,
            is_active=True,
        )
        db.add(user)
        permission_rows = []
        for code in permissions:
            permission = db.scalar(select(Permission).where(Permission.code == code))
            if permission is None:
                permission = Permission(
                    code=code,
                    name=code.replace("_", " ").title(),
                )
                db.add(permission)
            permission_rows.append(permission)
        db.flush()
        for permission in permission_rows:
            assignment = db.get(RolePermission, (role.id, permission.id))
            if assignment is None:
                db.add(RolePermission(role_id=role.id, permission_id=permission.id))
        token, _ = issue_session(db, user)
        db.flush()
        if expired:
            session = db.scalar(
                select(UserSession).where(
                    UserSession.token_hash == token_hash(token)
                )
            )
            session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        return token, branch.id


def _persist_identity(environment):
    shop_id = uuid.uuid4()
    with environment.session_factory() as db:
        db.add(ShopIdentity(shop_id=shop_id))
        db.commit()
    return shop_id


def test_valid_identity_preserves_rbac_and_session_protections(identity_app):
    _persist_identity(identity_app)
    cashier_token, _ = _create_user(
        identity_app,
        role_code="CASHIER",
        permissions=("SALE_CREATE", "ITEM_EDIT"),
    )

    with TestClient(identity_app.app) as client:
        created = client.post(
            "/api/v1/customers",
            json={"name": "Allowed customer"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        admin_only = client.post(
            "/api/v1/items/categories",
            json={"name": "Cashier forbidden category"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        expired_token, _ = _create_user(
            identity_app,
            role_code="CASHIER",
            permissions=("SALE_CREATE",),
            expired=True,
        )
        expired = client.post(
            "/api/v1/customers",
            json={"name": "Expired session customer"},
            headers={"Authorization": f"Bearer {expired_token}"},
        )

    assert created.status_code == 200
    assert admin_only.status_code == 403
    assert expired.status_code == 401


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/v1/customers", {"name": "Blocked customer"}),
        ("/api/v1/items/categories", {"name": "Blocked category"}),
    ],
)
def test_missing_identity_blocks_writes_across_business_domains_without_changes(
    identity_app, path, payload
):
    token, _ = _create_user(identity_app)
    before_file = identity_app.identity_file.read_bytes()

    with identity_app.session_factory() as db:
        identity_before = tuple(db.scalars(select(ShopIdentity)))
        customer_count_before = db.query(Customer).count()
        category_count_before = db.execute(
            text("SELECT count(*) FROM categories")
        ).scalar_one()

    with TestClient(identity_app.app) as client:
        response = client.post(
            path,
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    with identity_app.session_factory() as db:
        assert tuple(db.scalars(select(ShopIdentity))) == identity_before
        assert db.query(Customer).count() == customer_count_before
        assert db.execute(text("SELECT count(*) FROM categories")).scalar_one() == (
            category_count_before
        )
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Shop identity is not established; business writes are disabled."
    )
    assert identity_app.identity_file.read_bytes() == before_file


def test_recovery_state_blocks_business_writes_without_changes(identity_app):
    _persist_identity(identity_app)
    token, _ = _create_user(identity_app)
    write_restore_state(
        restore_state_path(identity_app.identity_file.parent / "backups"),
        state=RestoreState.RECOVERY_REQUIRED,
        phase="FAILED",
        operation_id=uuid.uuid4(),
        expected_shop_id=uuid.uuid4(),
        error="identity mismatch",
    )

    with TestClient(identity_app.app) as client:
        response = client.post(
            "/api/v1/customers",
            json={"name": "Blocked during recovery"},
            headers={"Authorization": f"Bearer {token}"},
        )

    with identity_app.session_factory() as db:
        assert db.query(Customer).count() == 0
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Restore recovery is incomplete; business writes are disabled."
    )


@pytest.mark.parametrize("state_file", ["missing", "malformed", "unreadable"])
def test_invalid_restore_state_blocks_business_writes_without_initializing(
    identity_app, state_file
):
    _persist_identity(identity_app)
    token, _ = _create_user(identity_app)
    backup_root = identity_app.identity_file.parent / "backups"
    state_path = restore_state_path(backup_root)
    if state_file == "missing":
        state_path.unlink()
    elif state_file == "malformed":
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("not-json", encoding="utf-8")
    elif state_file == "unreadable":
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.unlink()
        state_path.mkdir()

    with TestClient(identity_app.app) as client:
        response = client.post(
            "/api/v1/customers",
            json={"name": f"Blocked with {state_file} restore state"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Restore recovery state is unavailable; business writes are disabled."
    )
    if state_file == "missing":
        assert not state_path.exists()


@pytest.mark.parametrize("identity_version", [1, 2])
def test_malformed_or_inconsistent_identity_fails_closed_without_changes(
    identity_app, identity_version
):
    token, _ = _create_user(identity_app)
    raw_shop_id = (
        "not-a-uuid" if identity_version == 1 else str(uuid.uuid4())
    )
    with identity_app.engine.begin() as connection:
        if identity_version != 1:
            connection.exec_driver_sql("PRAGMA ignore_check_constraints = ON")
        connection.execute(
            text(
                "INSERT INTO shop_identity "
                "(identity_key, shop_id, identity_version, created_at) "
                "VALUES ('primary', :shop_id, :identity_version, CURRENT_TIMESTAMP)"
            ),
            {"shop_id": raw_shop_id, "identity_version": identity_version},
        )
        stored_identity = connection.execute(
            text("SELECT shop_id, identity_version FROM shop_identity")
        ).one()
    file_before = identity_app.identity_file.read_bytes()

    with TestClient(identity_app.app) as client:
        response = client.post(
            "/api/v1/customers",
            json={"name": "Malformed identity customer"},
            headers={"Authorization": f"Bearer {token}"},
        )

    with identity_app.engine.connect() as connection:
        assert connection.execute(
            text("SELECT shop_id, identity_version FROM shop_identity")
        ).one() == stored_identity
        assert connection.execute(text("SELECT count(*) FROM customers")).scalar_one() == 0
    assert response.status_code == 409
    assert identity_app.identity_file.read_bytes() == file_before


def test_populated_legacy_database_requires_enrollment_for_writes(identity_app):
    token, _ = _create_user(identity_app)
    with identity_app.session_factory() as db:
        db.add(Customer(name="Legacy customer"))
        db.commit()
        assert inspect_shop_identity(db).status is ShopIdentityStatus.ENROLLMENT_REQUIRED
        before_count = db.query(Customer).count()
    identity_before = identity_app.identity_file.read_bytes()

    with TestClient(identity_app.app) as client:
        response = client.post(
            "/api/v1/customers",
            json={"name": "Must not be added"},
            headers={"Authorization": f"Bearer {token}"},
        )

    with identity_app.session_factory() as db:
        assert db.query(Customer).count() == before_count
        assert db.query(ShopIdentity).count() == 0
    assert response.status_code == 409
    assert identity_app.identity_file.read_bytes() == identity_before


def test_health_discovery_recovery_and_read_only_report_remain_available(
    identity_app, monkeypatch
):
    admin_token, _ = _create_user(
        identity_app,
        permissions=("REPORT_VIEW", "BACKUP_MANAGE"),
    )

    monkeypatch.setattr(config.settings, "backup_root", str(identity_app.identity_file.parent / "backups"))

    def fail_without_database_access(**_kwargs):
        raise RuntimeError("isolated backup runner stub")

    monkeypatch.setattr(backup_module, "create_postgres_dump", fail_without_database_access)
    file_before = identity_app.identity_file.read_bytes()

    with TestClient(identity_app.app) as client:
        health_response = client.get("/health")
        readiness_response = client.get("/health/readiness")
        discovery_response = client.get("/discovery/info")
        recovery_response = client.post(
            "/api/v1/auth/admin/recovery-code",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        provisioning_response = client.post(
            "/api/v1/provisioning/shop",
            json={"branch_code": "SETUP", "branch_name": "Setup Branch"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        read_response = client.get(
            "/api/v1/customers",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        report_response = client.post(
            "/api/v1/reports/sales-summary",
            json={"start": "2026-01-01", "end": "2026-01-01"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        backup_response = client.post(
            "/api/v1/backup/create",
            json={"filename": "identity-gate-test.ltbak"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert health_response.status_code == 200
    assert readiness_response.status_code == 200
    assert discovery_response.status_code == 200
    assert discovery_response.json()["setup_state"] == "IDENTITY_ENROLLMENT_REQUIRED"
    assert recovery_response.status_code == 200
    assert provisioning_response.status_code == 401
    assert identity_app.identity_file.read_bytes() == file_before
    assert read_response.status_code == 200
    assert report_response.status_code == 200
    assert backup_response.status_code == 500
    assert backup_response.json()["detail"] == (
        "PostgreSQL backup failed: isolated backup runner stub"
    )
