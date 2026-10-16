import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import app.core.config as config
import app.api.routes.provisioning as provisioning_module
from app.api.deps import db_session
from app.api.routes.discovery import router as discovery_router
from app.api.routes.provisioning import router as provisioning_router
from app.db.session import Base
from app.models.auth import UserSession
from app.models.master import Branch, Permission, Role, RolePermission, User
from app.models.sales import Customer, Sale
from app.models.shop_identity import ShopIdentity
from app.core.restore_state import (
    RestoreState,
    RestoreStateError,
    initialize_restore_state,
    read_restore_state,
    restore_state_path,
    write_restore_state,
)
from app.core.shop_identity import (
    ShopIdentityError,
    ShopIdentityStatus,
    initialize_shop_identity,
    inspect_shop_identity,
)

_SUPPORTED_SCHEMA_REVISION = "0036_import_batch_idempotency"
_DOCUMENT_COUNTER_COLUMNS = {"prefix", "branch_id", "next_value"}


@pytest.fixture(autouse=True)
def use_isolated_test_environment(monkeypatch):
    monkeypatch.setattr(config.settings, "app_env", "test")
    monkeypatch.setattr(config.settings, "sqlite_bootstrap_fallback_enabled", True)


def _make_synthetic_database(
    tmp_path: Path,
    name: str,
    *,
    missing_table=None,
    missing_document_counters=False,
    missing_counter_column=None,
    schema_revision=_SUPPORTED_SCHEMA_REVISION,
    revision_column_length=64,
):
    database_path = tmp_path / name
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    tables = [
        table
        for table in Base.metadata.sorted_tables
        if table is not missing_table
    ]
    Base.metadata.create_all(engine, tables=tables)
    counter_columns = _DOCUMENT_COUNTER_COLUMNS - (
        {missing_counter_column} if missing_counter_column else set()
    )
    counter_definitions = {
        "prefix": "VARCHAR(20) NOT NULL",
        "branch_id": "VARCHAR(36) NOT NULL",
        "next_value": "BIGINT NOT NULL",
    }
    engine_schema = ", ".join(
        f"{column} {counter_definitions[column]}"
        for column in sorted(counter_columns)
    )
    primary_key = (
        ", PRIMARY KEY (prefix, branch_id)"
        if {"prefix", "branch_id"}.issubset(counter_columns)
        else ""
    )
    with engine.begin() as connection:
        if not missing_document_counters:
            connection.exec_driver_sql(
                f"CREATE TABLE document_counters ({engine_schema}{primary_key})"
            )
        connection.exec_driver_sql(
            "CREATE TABLE alembic_version "
            f"(version_num VARCHAR({revision_column_length}) NOT NULL)"
        )
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": schema_revision},
        )
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    return engine, session_factory, database_path


def _make_test_app(session_factory):
    def isolated_db_session():
        with session_factory() as db:
            yield db

    test_app = FastAPI()
    test_app.include_router(provisioning_router, prefix="/api/v1")
    test_app.include_router(discovery_router, prefix="/api/v1")
    test_app.dependency_overrides[db_session] = isolated_db_session
    return test_app


def _bootstrap_payload(branch_code="NEW-SHOP", admin_username="first-admin"):
    return {
        "branch_code": branch_code,
        "branch_name": "New Shop",
        "admin_username": admin_username,
        "admin_password": "AdminPass123!",
        "admin_display_name": "First Admin",
    }


def _snapshot_database(session_factory):
    with session_factory() as db:
        existing_tables = set(inspect(db.get_bind()).get_table_names())
        snapshot = {
            table.name: tuple(
                sorted(
                    (
                        tuple(
                            (column.name, row._mapping[column.name])
                            for column in table.columns
                        )
                        for row in db.execute(select(table))
                    ),
                    key=repr,
                )
            )
            for table in Base.metadata.sorted_tables
            if table.name in existing_tables and table.name != "shop_identity"
        }
        if "shop_identity" in existing_tables:
            snapshot["shop_identity"] = tuple(
                sorted(
                    (
                        tuple(row)
                        for row in db.execute(
                            text(
                                "SELECT identity_key, shop_id, identity_version, created_at "
                                "FROM shop_identity"
                            )
                        )
                    ),
                    key=repr,
                )
            )
        for table_name in ("document_counters", "alembic_version"):
            if table_name in existing_tables:
                table = Table(table_name, MetaData(), autoload_with=db.get_bind())
                snapshot[table_name] = tuple(sorted(
                    (tuple(row._mapping[column.name] for column in table.columns)
                     for row in db.execute(select(table))),
                    key=repr,
                ))
        return snapshot


def _seed_restored_shop(session_factory):
    with session_factory() as db:
        branch = Branch(code="RESTORED", name="Restored Shop", is_active=True)
        role = Role(code="ADMIN", name="Administrator", is_system=True)
        db.add_all([branch, role])
        db.flush()
        admin = User(
            username="restored-admin",
            password_hash="synthetic-test-hash",
            display_name="Restored Admin",
            role_id=role.id,
            branch_id=branch.id,
            is_active=True,
        )
        customer = Customer(name="Restored Customer", contact_no="TEST-001")
        db.add_all([admin, customer])
        db.flush()
        db.add(
            Sale(
                branch_id=branch.id,
                invoice_no="RESTORED-0001",
                customer_id=customer.id,
                sale_datetime=datetime.now(timezone.utc),
                cashier_id=admin.id,
                document_type="SALE",
                subtotal=Decimal("125.00"),
                discount_total=Decimal("0.00"),
                grand_total=Decimal("125.00"),
                total_cost=Decimal("75.00"),
                status="COMPLETED",
            )
        )
        db.commit()


@pytest.mark.parametrize("identity_state", ["missing_branch", "missing_file", "malformed"])
def test_restored_shop_without_valid_external_identity_is_unchanged(
    tmp_path, monkeypatch, identity_state
):
    identity_path = tmp_path / "instance.json"
    original_identity_contents = None
    if identity_state == "missing_branch":
        original_identity_contents = json.dumps({"instance_id": str(uuid.uuid4())})
        identity_path.write_text(original_identity_contents, encoding="utf-8")
    elif identity_state == "malformed":
        original_identity_contents = '{"instance_id": '
        identity_path.write_text(original_identity_contents, encoding="utf-8")
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))

    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path, "restored-shop.sqlite3"
    )
    _seed_restored_shop(session_factory)
    before = _snapshot_database(session_factory)

    with TestClient(_make_test_app(session_factory)) as client:
        response = client.post(
            "/api/v1/provisioning/bootstrap",
            json=_bootstrap_payload("UNEXPECTED-SHOP", "unexpected-admin"),
        )

    after = _snapshot_database(session_factory)
    identity_exists_after = identity_path.exists()
    identity_contents_after = (
        identity_path.read_text(encoding="utf-8") if identity_exists_after else None
    )
    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    assert response.status_code == 409
    assert "existing shop state" in response.json()["detail"]
    assert after == before
    assert identity_exists_after is (original_identity_contents is not None)
    assert identity_contents_after == original_identity_contents
    engine.dispose()


def test_incomplete_schema_fails_closed_without_identity_or_row_changes(
    tmp_path, monkeypatch
):
    identity = {"instance_id": str(uuid.uuid4())}
    identity_path = tmp_path / "instance.json"
    original_identity_contents = json.dumps(identity)
    identity_path.write_text(original_identity_contents, encoding="utf-8")
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))

    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path, "incomplete-schema.sqlite3", missing_table=Sale.__table__
    )
    before = _snapshot_database(session_factory)
    with TestClient(_make_test_app(session_factory)) as client:
        response = client.post(
            "/api/v1/provisioning/bootstrap",
            json=_bootstrap_payload(),
        )

    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    assert response.status_code == 503
    assert "schema is incomplete" in response.json()["detail"]
    assert _snapshot_database(session_factory) == before
    assert identity_path.read_text(encoding="utf-8") == original_identity_contents
    engine.dispose()


@pytest.mark.parametrize(
    ("database_name", "database_options", "expected_detail"),
    [
        (
            "unsupported-revision.sqlite3",
            {"schema_revision": "0029_credit_settlement_version"},
            "Unsupported database schema revision",
        ),
        (
            "missing-counter-column.sqlite3",
            {"missing_counter_column": "next_value"},
            "Database schema is incomplete",
        ),
        (
            "undersized-revision-column.sqlite3",
            {"revision_column_length": 32},
            "Database schema is incomplete",
        ),
        (
            "missing-document-counters.sqlite3",
            {"missing_document_counters": True},
            "Database schema is incomplete",
        ),
    ],
)
def test_unsupported_schema_fails_closed_without_identity_or_row_changes(
    tmp_path, monkeypatch, database_name, database_options, expected_detail
):
    identity = {"instance_id": str(uuid.uuid4())}
    identity_path = tmp_path / "instance.json"
    original_identity_contents = json.dumps(identity)
    identity_path.write_text(original_identity_contents, encoding="utf-8")
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))

    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path, database_name, **database_options
    )
    before = _snapshot_database(session_factory)
    with TestClient(_make_test_app(session_factory)) as client:
        response = client.post(
            "/api/v1/provisioning/bootstrap",
            json=_bootstrap_payload(),
        )

    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    assert response.status_code == 503
    assert expected_detail in response.json()["detail"]
    assert _snapshot_database(session_factory) == before
    assert identity_path.read_text(encoding="utf-8") == original_identity_contents
    engine.dispose()


def test_role_permission_assignments_count_as_existing_state(tmp_path, monkeypatch):
    identity = {"instance_id": str(uuid.uuid4())}
    identity_path = tmp_path / "instance.json"
    original_identity_contents = json.dumps(identity)
    identity_path.write_text(original_identity_contents, encoding="utf-8")
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))

    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path, "authorization-state.sqlite3"
    )
    with session_factory() as db:
        role = Role(code="PRESEEDED", name="Preseeded", is_system=True)
        permission = Permission(
            code="PRESEEDED_PERMISSION",
            name="Preseeded permission",
        )
        db.add_all([role, permission])
        db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))
        db.commit()
    before = _snapshot_database(session_factory)

    with TestClient(_make_test_app(session_factory)) as client:
        response = client.post(
            "/api/v1/provisioning/bootstrap",
            json=_bootstrap_payload(),
        )

    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    assert response.status_code == 409
    assert _snapshot_database(session_factory) == before
    assert identity_path.read_text(encoding="utf-8") == original_identity_contents
    engine.dispose()


def test_document_counter_rows_count_as_existing_state_without_identity_changes(
    tmp_path, monkeypatch
):
    identity = {"instance_id": str(uuid.uuid4())}
    identity_path = tmp_path / "instance.json"
    original_identity_contents = json.dumps(identity)
    identity_path.write_text(original_identity_contents, encoding="utf-8")
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))

    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path, "document-counter-state.sqlite3"
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO document_counters (prefix, branch_id, next_value) "
                "VALUES ('SALE', :branch_id, 2)"
            ),
            {"branch_id": str(uuid.uuid4())},
        )
    before = _snapshot_database(session_factory)
    with TestClient(_make_test_app(session_factory)) as client:
        response = client.post(
            "/api/v1/provisioning/bootstrap",
            json=_bootstrap_payload(),
        )

    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    assert response.status_code == 409
    assert "existing shop state" in response.json()["detail"]
    assert _snapshot_database(session_factory) == before
    assert identity_path.read_text(encoding="utf-8") == original_identity_contents
    engine.dispose()


@pytest.mark.parametrize("app_env", ["test", "development"])
def test_complete_empty_schema_allows_first_time_bootstrap(
    tmp_path, monkeypatch, app_env
):
    identity = {"instance_id": str(uuid.uuid4())}
    identity_path = tmp_path / "instance.json"
    identity_path.write_text(json.dumps(identity), encoding="utf-8")
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))
    monkeypatch.setattr(config.settings, "app_env", app_env)
    monkeypatch.setattr(config.settings, "sqlite_bootstrap_fallback_enabled", True)

    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path, "new-shop.sqlite3"
    )
    assert set(Base.metadata.tables).issubset(set(inspect(engine).get_table_names()))
    assert {"document_counters", "alembic_version"}.issubset(
        set(inspect(engine).get_table_names())
    )

    with TestClient(_make_test_app(session_factory)) as client:
        response = client.post(
            "/api/v1/provisioning/bootstrap",
            json=_bootstrap_payload(),
        )

    with session_factory() as db:
        branch = db.scalar(select(Branch).where(Branch.code == "NEW-SHOP"))
        admin = db.scalar(select(User).where(User.username == "first-admin"))
        assert branch is not None
        assert admin is not None
        assert admin.branch_id == branch.id
        assert len(tuple(db.scalars(select(UserSession)))) == 1

    identity_after = json.loads(identity_path.read_text(encoding="utf-8"))
    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    assert response.status_code == 200
    assert response.json()["setup_state"] == "READY"
    assert response.json()["instance_id"] == identity["instance_id"]
    assert identity_after == {**identity, "branch_code": "NEW-SHOP"}
    engine.dispose()


def test_identity_persistence_failure_retry_fails_closed_without_duplicate_or_rebinding(
    tmp_path, monkeypatch
):
    instance_identity = {"instance_id": str(uuid.uuid4())}
    identity_path = tmp_path / "instance.json"
    original_identity_contents = json.dumps(instance_identity)
    identity_path.write_text(original_identity_contents, encoding="utf-8")
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))
    monkeypatch.setattr(config.settings, "app_env", "test")
    monkeypatch.setattr(config.settings, "sqlite_bootstrap_fallback_enabled", True)

    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path, "identity-save-failure.sqlite3"
    )

    def fail_identity_write(_branch_code):
        raise OSError("synthetic identity write failure")

    monkeypatch.setattr(
        provisioning_module,
        "save_branch_code",
        fail_identity_write,
    )
    app = _make_test_app(session_factory)

    with TestClient(app) as client:
        first_response = client.post(
            "/api/v1/provisioning/bootstrap",
            json=_bootstrap_payload("RECOVER-ME", "first-admin"),
        )

    after_first_attempt = _snapshot_database(session_factory)
    first_identity_contents = identity_path.read_text(encoding="utf-8")
    with session_factory() as db:
        first_branch = db.scalar(select(Branch).where(Branch.code == "RECOVER-ME"))
        first_admin = db.scalar(select(User).where(User.username == "first-admin"))
        first_sessions = tuple(db.scalars(select(UserSession)))
        assert first_branch is not None
        assert first_admin is not None
        assert first_admin.branch_id == first_branch.id
        assert len(first_sessions) == 1

    with TestClient(app) as client:
        retry_response = client.post(
            "/api/v1/provisioning/bootstrap",
            json=_bootstrap_payload("SECOND-SHOP", "second-admin"),
        )

    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    assert first_response.status_code == 500
    assert "EXISTING_SHOP_REQUIRED" in first_response.json()["detail"]
    assert first_identity_contents == original_identity_contents
    assert retry_response.status_code == 409
    assert "existing shop state" in retry_response.json()["detail"]
    assert _snapshot_database(session_factory) == after_first_attempt
    assert identity_path.read_text(encoding="utf-8") == original_identity_contents
    with session_factory() as db:
        assert len(tuple(db.scalars(select(Branch)))) == 1
        assert len(tuple(db.scalars(select(User)))) == 1
        assert len(tuple(db.scalars(select(UserSession)))) == 1
        assert db.scalar(select(Branch).where(Branch.code == "SECOND-SHOP")) is None
        assert db.scalar(select(User).where(User.username == "second-admin")) is None
    engine.dispose()


def test_sqlite_bootstrap_is_rejected_in_production_without_changes(
    tmp_path, monkeypatch
):
    identity = {"instance_id": str(uuid.uuid4())}
    identity_path = tmp_path / "instance.json"
    original_identity_contents = json.dumps(identity)
    identity_path.write_text(original_identity_contents, encoding="utf-8")
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))
    monkeypatch.setattr(config.settings, "app_env", "production")
    monkeypatch.setattr(config.settings, "sqlite_bootstrap_fallback_enabled", True)

    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path, "production-sqlite.sqlite3"
    )
    before = _snapshot_database(session_factory)
    with TestClient(_make_test_app(session_factory)) as client:
        response = client.post(
            "/api/v1/provisioning/bootstrap",
            json=_bootstrap_payload(),
        )

    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    assert response.status_code == 503
    assert "explicit test/development" in response.json()["detail"]
    assert _snapshot_database(session_factory) == before
    assert identity_path.read_text(encoding="utf-8") == original_identity_contents
    engine.dispose()


@pytest.mark.parametrize("app_env", ["test", "development"])
def test_sqlite_bootstrap_without_explicit_opt_in_is_rejected_unchanged(
    tmp_path, monkeypatch, app_env
):
    identity = {"instance_id": str(uuid.uuid4())}
    identity_path = tmp_path / "instance.json"
    original_identity_contents = json.dumps(identity)
    identity_path.write_text(original_identity_contents, encoding="utf-8")
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))
    monkeypatch.setattr(config.settings, "app_env", app_env)
    monkeypatch.setattr(config.settings, "sqlite_bootstrap_fallback_enabled", False)

    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path, f"{app_env}-without-sqlite-opt-in.sqlite3"
    )
    before = _snapshot_database(session_factory)
    with TestClient(_make_test_app(session_factory)) as client:
        response = client.post(
            "/api/v1/provisioning/bootstrap",
            json=_bootstrap_payload(),
        )

    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    assert response.status_code == 503
    assert "explicit test/development" in response.json()["detail"]
    assert _snapshot_database(session_factory) == before
    assert identity_path.read_text(encoding="utf-8") == original_identity_contents
    engine.dispose()


@pytest.mark.parametrize("app_env", [None, "", "staging"])
def test_sqlite_bootstrap_with_missing_or_unknown_environment_is_rejected_unchanged(
    tmp_path, monkeypatch, app_env
):
    identity = {"instance_id": str(uuid.uuid4())}
    identity_path = tmp_path / "instance.json"
    original_identity_contents = json.dumps(identity)
    identity_path.write_text(original_identity_contents, encoding="utf-8")
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))
    monkeypatch.setattr(config.settings, "app_env", app_env)
    monkeypatch.setattr(config.settings, "sqlite_bootstrap_fallback_enabled", True)

    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path,
        f"invalid-env-{str(app_env).lower() or 'missing'}-sqlite.sqlite3",
    )
    before = _snapshot_database(session_factory)
    with TestClient(_make_test_app(session_factory)) as client:
        response = client.post(
            "/api/v1/provisioning/bootstrap",
            json=_bootstrap_payload(),
        )

    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    assert response.status_code == 503
    assert "explicit test/development" in response.json()["detail"]
    assert _snapshot_database(session_factory) == before
    assert identity_path.read_text(encoding="utf-8") == original_identity_contents
    engine.dispose()


def test_concurrent_bootstrap_requests_initialize_only_once(tmp_path, monkeypatch):
    identity = {"instance_id": str(uuid.uuid4())}
    identity_path = tmp_path / "instance.json"
    identity_path.write_text(json.dumps(identity), encoding="utf-8")
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))

    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path, "concurrent-bootstrap.sqlite3"
    )
    test_app = _make_test_app(session_factory)

    def send_bootstrap(branch_code, username):
        with TestClient(test_app) as client:
            return client.post(
                "/api/v1/provisioning/bootstrap",
                json=_bootstrap_payload(branch_code, username),
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = (
            executor.submit(send_bootstrap, "CONCURRENT-A", "admin-a"),
            executor.submit(send_bootstrap, "CONCURRENT-B", "admin-b"),
        )
        responses = [future.result(timeout=30) for future in futures]

    with session_factory() as db:
        branches = tuple(db.scalars(select(Branch)))
        admins = tuple(db.scalars(select(User)))
        sessions = tuple(db.scalars(select(UserSession)))
        shop_identities = tuple(db.scalars(select(ShopIdentity)))

    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert len(branches) == 1
    assert len(admins) == 1
    assert len(sessions) == 1
    assert len(shop_identities) == 1
    assert shop_identities[0].identity_version == 1
    assert isinstance(shop_identities[0].shop_id, uuid.UUID)
    assert json.loads(identity_path.read_text(encoding="utf-8")) == {
        **identity,
        "branch_code": branches[0].code,
    }
    engine.dispose()


def test_empty_database_initializes_one_versioned_identity_idempotently(tmp_path):
    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path, "shop-identity-empty.sqlite3"
    )
    with session_factory() as db:
        before = _snapshot_database(session_factory)
        inspection = inspect_shop_identity(db)
        first_shop_id = initialize_shop_identity(db)
        db.commit()
    with session_factory() as db:
        second_shop_id = initialize_shop_identity(db)
        db.commit()
        identities = tuple(db.scalars(select(ShopIdentity)))

    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    assert inspection.status is ShopIdentityStatus.EMPTY
    assert first_shop_id == second_shop_id
    assert len(identities) == 1
    assert identities[0].shop_id == first_shop_id
    assert identities[0].identity_version == 1
    assert before["shop_identity"] == ()
    engine.dispose()


def test_populated_legacy_database_requires_enrollment_without_changes(
    tmp_path, monkeypatch
):
    identity_path = tmp_path / "instance.json"
    original_identity = json.dumps({"instance_id": str(uuid.uuid4())})
    identity_path.write_text(original_identity, encoding="utf-8")
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))

    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path, "shop-identity-legacy.sqlite3"
    )
    _seed_restored_shop(session_factory)
    before = _snapshot_database(session_factory)

    with session_factory() as db:
        inspection = inspect_shop_identity(db)
        with pytest.raises(ShopIdentityError, match="enrollment is required"):
            initialize_shop_identity(db)

    with TestClient(_make_test_app(session_factory)) as client:
        response = client.get("/api/v1/discovery/info")

    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    assert inspection.status is ShopIdentityStatus.ENROLLMENT_REQUIRED
    assert response.status_code == 200
    assert response.json()["setup_state"] == "IDENTITY_ENROLLMENT_REQUIRED"
    assert _snapshot_database(session_factory) == before
    assert identity_path.read_text(encoding="utf-8") == original_identity
    engine.dispose()


def test_malformed_shop_identity_fails_closed_without_row_changes(
    tmp_path, monkeypatch
):
    identity_path = tmp_path / "instance.json"
    original_identity = json.dumps({"instance_id": str(uuid.uuid4())})
    identity_path.write_text(original_identity, encoding="utf-8")
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))
    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path, "shop-identity-malformed.sqlite3"
    )
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO shop_identity "
            "(identity_key, shop_id, identity_version, created_at) "
            "VALUES ('primary', 'not-a-uuid', 1, CURRENT_TIMESTAMP)"
        )
    before = _snapshot_database(session_factory)

    with session_factory() as db:
        inspection = inspect_shop_identity(db)
        with pytest.raises(ShopIdentityError, match="enrollment is required"):
            initialize_shop_identity(db)

    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    assert inspection.status is ShopIdentityStatus.INVALID
    assert _snapshot_database(session_factory) == before
    assert identity_path.read_text(encoding="utf-8") == original_identity
    engine.dispose()


def test_valid_persisted_shop_identity_is_returned_unchanged(tmp_path):
    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path, "shop-identity-valid.sqlite3"
    )
    expected_shop_id = uuid.uuid4()
    with session_factory() as db:
        db.add(ShopIdentity(shop_id=expected_shop_id))
        db.commit()
    before = _snapshot_database(session_factory)

    with session_factory() as db:
        inspection = inspect_shop_identity(db)
        actual_shop_id = initialize_shop_identity(db)
        db.commit()

    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    assert inspection.status is ShopIdentityStatus.PRESENT
    assert inspection.shop_id == expected_shop_id
    assert actual_shop_id == expected_shop_id
    assert _snapshot_database(session_factory) == before
    engine.dispose()
    engine.dispose()


def test_shop_identity_migration_is_additive_and_enforces_immutability(tmp_path):
    database_path = tmp_path / "shop-identity-migration.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}")
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0032_shop_identity_metadata.py"
    )
    spec = importlib.util.spec_from_file_location(
        "shop_identity_migration", migration_path
    )
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE branches (id VARCHAR(36) PRIMARY KEY, code VARCHAR(30))"
        )
        connection.exec_driver_sql(
            "INSERT INTO branches (id, code) VALUES ('legacy-branch-id', 'LEGACY')"
        )
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
        assert inspect(connection).has_table("branches")
        assert inspect(connection).has_table("shop_identity")
        assert connection.execute(
            text("SELECT code FROM branches WHERE id = 'legacy-branch-id'")
        ).scalar_one() == "LEGACY"
        connection.execute(
            text(
                "INSERT INTO shop_identity "
                "(identity_key, shop_id, identity_version) "
                "VALUES ('primary', :shop_id, 1)"
            ),
            {"shop_id": str(uuid.uuid4())},
        )

    with pytest.raises(
        IntegrityError, match="Canonical shop identity cannot be changed"
    ):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE shop_identity SET shop_id = :shop_id "
                    "WHERE identity_key = 'primary'"
                ),
                {"shop_id": str(uuid.uuid4())},
            )
    with pytest.raises(
        IntegrityError, match="Canonical shop identity cannot be deleted"
    ):
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM shop_identity WHERE identity_key = 'primary'")
            )

    assert engine.url.get_backend_name() == "sqlite"
    assert database_path.resolve().parent == tmp_path.resolve()
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT count(*) FROM shop_identity")
        ).scalar_one() == 1
    engine.dispose()


def test_bootstrap_blocks_non_ready_restore_state_without_database_changes(
    tmp_path, monkeypatch
):
    identity_path = tmp_path / "instance.json"
    identity_path.write_text(json.dumps({"instance_id": str(uuid.uuid4())}), encoding="utf-8")
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(config.settings, "backup_root", str(backup_root))
    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path, "bootstrap-restore-in-progress.sqlite3"
    )
    operation_id = uuid.uuid4()
    write_restore_state(
        restore_state_path(backup_root),
        state=RestoreState.RESTORE_IN_PROGRESS,
        phase="BEFORE_REPLACEMENT",
        operation_id=operation_id,
        expected_shop_id=uuid.uuid4(),
    )
    before = _snapshot_database(session_factory)

    with TestClient(_make_test_app(session_factory)) as client:
        response = client.post(
            "/api/v1/provisioning/bootstrap",
            json=_bootstrap_payload(),
        )

    assert response.status_code == 503
    assert "Restore recovery is incomplete" in response.json()["detail"]
    assert _snapshot_database(session_factory) == before
    assert read_restore_state(restore_state_path(backup_root)).state is RestoreState.RESTORE_IN_PROGRESS
    engine.dispose()


def test_bootstrap_state_initialization_failure_precedes_database_mutation(
    tmp_path, monkeypatch
):
    identity_path = tmp_path / "instance.json"
    identity_path.write_text(json.dumps({"instance_id": str(uuid.uuid4())}), encoding="utf-8")
    monkeypatch.setattr(config.settings, "instance_id_file", str(identity_path))
    monkeypatch.setattr(config.settings, "backup_root", str(tmp_path / "backups"))
    engine, session_factory, database_path = _make_synthetic_database(
        tmp_path, "bootstrap-state-write-failure.sqlite3"
    )
    before = _snapshot_database(session_factory)

    def fail_state_initialization(_backup_root):
        raise OSError("state storage unavailable")

    monkeypatch.setattr(
        provisioning_module, "initialize_restore_state", fail_state_initialization
    )
    with TestClient(_make_test_app(session_factory)) as client:
        response = client.post(
            "/api/v1/provisioning/bootstrap",
            json=_bootstrap_payload(),
        )

    assert response.status_code == 503
    assert "state is unavailable" in response.json()["detail"]
    assert _snapshot_database(session_factory) == before
    engine.dispose()


def test_restore_interlock_rejects_same_root_contention(tmp_path):
    from app.core.restore_state import (
        RestoreInterlockBusy,
        acquire_restore_interlock,
    )

    with acquire_restore_interlock(tmp_path):
        with pytest.raises(RestoreInterlockBusy):
            with acquire_restore_interlock(tmp_path):
                pass


@pytest.mark.parametrize(
    "existing_state", ["ready", "in_progress", "recovery_required", "malformed", "unreadable"]
)
def test_restore_state_initialization_never_overwrites_existing_state(
    tmp_path, existing_state
):
    backup_root = tmp_path / "backups"
    state_path = restore_state_path(backup_root)
    if existing_state == "ready":
        write_restore_state(state_path, state=RestoreState.READY, phase="EXISTING")
    elif existing_state in {"in_progress", "recovery_required"}:
        write_restore_state(
            state_path,
            state=(
                RestoreState.RESTORE_IN_PROGRESS
                if existing_state == "in_progress"
                else RestoreState.RECOVERY_REQUIRED
            ),
            phase="EXISTING",
            operation_id=uuid.uuid4(),
            expected_shop_id=uuid.uuid4(),
        )
    elif existing_state == "malformed":
        state_path.parent.mkdir(parents=True)
        state_path.write_text("{malformed", encoding="utf-8")
    else:
        state_path.parent.mkdir(parents=True)
        state_path.mkdir()

    original = (
        state_path.read_bytes()
        if state_path.is_file()
        else tuple(state_path.iterdir())
    )
    if existing_state in {"malformed", "unreadable"}:
        with pytest.raises(RestoreStateError):
            initialize_restore_state(backup_root)
    else:
        record = initialize_restore_state(backup_root)
        expected = {
            "ready": RestoreState.READY,
            "in_progress": RestoreState.RESTORE_IN_PROGRESS,
            "recovery_required": RestoreState.RECOVERY_REQUIRED,
        }[existing_state]
        assert record.state is expected

    assert (
        state_path.read_bytes()
        if state_path.is_file()
        else tuple(state_path.iterdir())
    ) == original
