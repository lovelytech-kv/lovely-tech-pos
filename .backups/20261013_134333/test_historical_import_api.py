"""Focused tests for historical spreadsheet Upload & Preview API (Packet 3).

All tests use an isolated in-memory or temporary SQLite database — never the
real shop database.  Each test gets a fresh database with shop identity and
restore state pre-seeded so that the write-gate passes for authenticated ADMIN
requests.
"""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

import app.core.config as config
from app.api.deps import db_session, issue_session
from app.api.router import api_router
from app.core.restore_state import (
    RestoreState,
    restore_state_path,
    write_restore_state,
)
from app.db.base import Base
from app.models.import_staging import ImportBatch, ImportStagingRow
from app.models.inventory import (
    FifoAllocation,
    Purchase,
    PurchaseLine,
    PurchaseLot,
    StockMovement,
)
from app.models.master import (
    Branch,
    Category,
    Item,
    ItemType,
    Permission,
    Role,
    RolePermission,
    User,
)
from app.models.sales import Customer, Payment, Sale, SaleLine
from app.models.shop_identity import ShopIdentity


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ITEM_VALID_CSV = (
    b"ITEM CODE,DESCRIPTION,SALE PRICE\n"
    b"LVT001,Item One,100.0\n"
    b"LVT002,Item Two,200.0"
)

PURCHASE_VALID_CSV = (
    b"DATE,ITEM CODE,UNIT PRICE,QUANTITY\n"
    b"2024-10-01T00:00:00,LVT001,80.50,18"
)

SALE_VALID_CSV = (
    b"DATE,ITEM CODE,SALE PRICE,QUANTITY\n"
    b"2024-10-01T00:00:00,LVT001,900,4"
)

ITEM_MIXED_CSV = (
    b"ITEM CODE,DESCRIPTION,SALE PRICE\n"
    b"LVT001,Valid Item,100.0\n"
    b"LVT002,,200.0\n"
    b"LVT003,Valid Item 3,300.0\n"
    b",Missing Code,400.0\n"
    b"LVT005,Valid Item 5,500.0"
)

ITEM_MISSING_COLUMNS_CSV = b"ITEM CODE,SALE PRICE\nLVT001,100.0\nLVT002,200.0"

DUPLICATE_HEADERS_CSV = (
    b"ITEM CODE,ITEM CODE,DESCRIPTION\nLVT001,LVT002,Test"
)

MALFORMED_UTF8_CSV = b"\xff\xfe\xfd\xfc"

ITEM_PAGINATED_CSV = (
    b"ITEM CODE,DESCRIPTION,SALE PRICE\n"
    + b"".join(
        f"LVT{i:04d},Item {i},{i * 100:.1f}\n".encode() for i in range(1, 11)
    )
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def import_env(tmp_path, monkeypatch):
    """Isolated SQLite test environment with shop identity and restore state."""

    monkeypatch.setattr(config.settings, "app_env", "test")
    monkeypatch.setattr(config.settings, "sqlite_bootstrap_fallback_enabled", True)
    monkeypatch.setattr(config.settings, "backup_root", str(tmp_path / "backups"))
    monkeypatch.setattr(
        config.settings, "instance_id_file", str(tmp_path / "instance.json")
    )

    identity_file = tmp_path / "instance.json"
    identity_file.write_text(
        json.dumps({"instance_id": str(uuid.uuid4())}), encoding="utf-8"
    )

    write_restore_state(
        restore_state_path(tmp_path / "backups"),
        state=RestoreState.READY,
        phase="TEST_INITIALIZED",
    )

    database_path = tmp_path / "import-test.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE document_counters ("
            "prefix VARCHAR(20) NOT NULL, branch_id VARCHAR(36) NOT NULL, "
            "next_value BIGINT NOT NULL, PRIMARY KEY (prefix, branch_id))"
        )
        connection.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(64) NOT NULL)"
        )
        connection.execute(
            text(
                "INSERT INTO alembic_version (version_num) VALUES (:revision)"
            ),
            {"revision": "0033_historical_import_staging"},
        )

    session_factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )

    def isolated_db_session():
        with session_factory() as db:
            yield db

    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[db_session] = isolated_db_session

    shop_id = uuid.uuid4()
    with session_factory() as db:
        db.add(ShopIdentity(shop_id=shop_id))
        db.commit()

    yield SimpleNamespace(
        app=app,
        engine=engine,
        session_factory=session_factory,
        tmp_path=tmp_path,
    )

    engine.dispose()


def _create_user(environment, *, role_code="ADMIN", permissions=("IMPORT_MANAGE",)):
    """Create a user with a session token. Returns dict with token, user_id, branch_id."""
    with environment.session_factory() as db:
        branch = Branch(
            code=f"BR-{uuid.uuid4().hex[:8]}", name="Test Branch"
        )
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

        perm_objects = []
        for code in permissions:
            perm = db.scalar(select(Permission).where(Permission.code == code))
            if perm is None:
                perm = Permission(
                    code=code, name=code.replace("_", " ").title()
                )
                db.add(perm)
            perm_objects.append(perm)

        db.flush()
        for perm in perm_objects:
            assignment = db.get(RolePermission, (role.id, perm.id))
            if assignment is None:
                db.add(
                    RolePermission(role_id=role.id, permission_id=perm.id)
                )

        token, _ = issue_session(db, user)
        db.commit()
        return {
            "token": token,
            "user_id": str(user.id),
            "branch_id": str(branch.id),
        }


def _count_business_records(db):
    """Count rows in operational business tables."""
    return {
        "items": db.query(Item).count(),
        "categories": db.query(Category).count(),
        "item_types": db.query(ItemType).count(),
        "purchases": db.query(Purchase).count(),
        "purchase_lines": db.query(PurchaseLine).count(),
        "purchase_lots": db.query(PurchaseLot).count(),
        "sales": db.query(Sale).count(),
        "sale_lines": db.query(SaleLine).count(),
        "payments": db.query(Payment).count(),
        "customers": db.query(Customer).count(),
        "stock_movements": db.query(StockMovement).count(),
        "fifo_allocations": db.query(FifoAllocation).count(),
    }


# ---------------------------------------------------------------------------
# 1. Successful upload of each supported import type
# ---------------------------------------------------------------------------

def test_upload_valid_item(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=items.csv",
            content=ITEM_VALID_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert response.status_code == 200
    body = response.json()
    assert "batch_id" in body
    assert body["total_rows"] == 2
    assert body["valid_rows"] == 2
    assert body["invalid_rows"] == 0


def test_upload_valid_purchase(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=PURCHASE&filename=purchases.csv",
            content=PURCHASE_VALID_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert response.status_code == 200
    body = response.json()
    assert "batch_id" in body
    assert body["total_rows"] == 1
    assert body["valid_rows"] == 1


def test_upload_valid_sale(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=SALE&filename=sales.csv",
            content=SALE_VALID_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert response.status_code == 200
    body = response.json()
    assert "batch_id" in body
    assert body["total_rows"] == 1
    assert body["valid_rows"] == 1


# ---------------------------------------------------------------------------
# 2. Missing / invalid import type
# ---------------------------------------------------------------------------

def test_upload_missing_import_type(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?filename=test.csv",
            content=ITEM_VALID_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert response.status_code == 422


def test_upload_invalid_import_type(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=UNKNOWN&filename=test.csv",
            content=ITEM_VALID_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert response.status_code == 400
    assert "Invalid import type" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 3. Missing file, empty file, unsupported extension, malformed CSV
# ---------------------------------------------------------------------------

def test_upload_empty_file(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=test.csv",
            content=b"",
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_upload_missing_file(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=test.csv",
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_upload_unsupported_extension(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=test.txt",
            content=ITEM_VALID_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_upload_malformed_csv(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=test.csv",
            content=MALFORMED_UTF8_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert response.status_code == 400
    assert "UTF-8" in response.json()["detail"]


def test_upload_too_many_rows(import_env, monkeypatch):
    admin = _create_user(import_env)
    monkeypatch.setattr(
        "app.api.routes.historical_import.MAX_IMPORT_ROWS", 3
    )
    csv_content = (
        b"ITEM CODE,DESCRIPTION,SALE PRICE\n"
        b"LVT001,Item 1,100.0\nLVT002,Item 2,200.0\nLVT003,Item 3,300.0\n"
        b"LVT004,Item 4,400.0"
    )
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=test.csv",
            content=csv_content,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert response.status_code == 400
    assert "Too many rows" in response.json()["detail"]


def test_upload_file_too_large(import_env, monkeypatch):
    admin = _create_user(import_env)
    monkeypatch.setattr(
        "app.api.routes.historical_import.MAX_UPLOAD_BYTES", 50
    )
    csv_content = b"ITEM CODE,DESCRIPTION,SALE PRICE\nLVT001,Item 1,100.0\n" * 10
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=test.csv",
            content=csv_content,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. Missing required columns and duplicate / colliding headers
# ---------------------------------------------------------------------------

def test_upload_missing_required_columns(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=test.csv",
            content=ITEM_MISSING_COLUMNS_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert response.status_code == 200
    body = response.json()
    batch_id = body["batch_id"]
    assert body["total_rows"] == 2
    assert body["valid_rows"] == 0
    assert body["invalid_rows"] == 2

    preview = client.get(
        f"/api/v1/import/preview/{batch_id}",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert preview.status_code == 200
    pv = preview.json()
    assert pv["total_rows"] == 2
    assert pv["valid_rows"] == 0
    assert pv["invalid_rows"] == 2
    assert all(
        "DESCRIPTION" in (e["error"] or "")
        for e in pv["invalid_details"]
    )


def test_upload_duplicate_headers(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=test.csv",
            content=DUPLICATE_HEADERS_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert response.status_code == 400
    assert "colliding" in response.json()["detail"].lower() or \
           "duplicate" in response.json()["detail"].lower()
    with import_env.session_factory() as db:
        assert db.query(ImportBatch).count() == 0


# ---------------------------------------------------------------------------
# 5. Valid and invalid rows in the same file
# ---------------------------------------------------------------------------

def test_upload_valid_and_invalid_rows(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=mixed.csv",
            content=ITEM_MIXED_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["total_rows"] == 5
    assert body["valid_rows"] == 3
    assert body["invalid_rows"] == 2
    batch_id = body["batch_id"]

    preview = client.get(
        f"/api/v1/import/preview/{batch_id}",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert preview.status_code == 200
    pv = preview.json()
    assert pv["total_rows"] == 5
    assert pv["valid_rows"] == 3
    assert pv["invalid_rows"] == 2
    assert len(pv["invalid_details"]) == 2
    row_numbers = {d["row_number"] for d in pv["invalid_details"]}
    assert row_numbers == {3, 5}


# ---------------------------------------------------------------------------
# 6. Batch and staging-row persistence (row numbers + validation errors)
# ---------------------------------------------------------------------------

def test_batch_and_staging_row_persistence(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=items.csv",
            content=ITEM_VALID_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert response.status_code == 200
    batch_id = response.json()["batch_id"]

    with import_env.session_factory() as db:
        batch = db.query(ImportBatch).filter(ImportBatch.id == uuid.UUID(batch_id)).first()
        assert batch is not None
        assert batch.status == "PENDING_APPROVAL"
        assert batch.filename == "items.csv"
        assert str(batch.uploaded_by) == admin["user_id"]

        rows = (
            db.query(ImportStagingRow)
            .filter(ImportStagingRow.batch_id == uuid.UUID(batch_id))
            .order_by(ImportStagingRow.row_number)
            .all()
        )
        assert len(rows) == 2
        assert rows[0].row_number == 2
        assert rows[1].row_number == 3
        assert rows[0].row_type == "ITEM"
        assert rows[0].validation_status == "VALID"
        assert rows[0].error_details is None
        assert rows[0].raw_data["ITEM CODE"] == "LVT001"


# ---------------------------------------------------------------------------
# 7. Database rollback on an injected persistence failure
# ---------------------------------------------------------------------------

def test_upload_rollback_on_persistence_failure(import_env):
    admin = _create_user(import_env)
    call_count = {"n": 0}
    original_commit = Session.commit

    def patched_commit(self):
        call_count["n"] += 1
        if call_count["n"] > 1:
            raise Exception("Simulated DB failure")
        return original_commit(self)

    csv_content = (
        b"ITEM CODE,DESCRIPTION,SALE PRICE\nLVT001,Item 1,100.0"
    )
    with TestClient(import_env.app) as client:
        with patch.object(Session, "commit", patched_commit):
            response = client.post(
                "/api/v1/import/upload?import_type=ITEM&filename=test.csv",
                content=csv_content,
                headers={"Authorization": f"Bearer {admin['token']}"},
            )

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error during upload staging."

    with import_env.session_factory() as db:
        assert db.query(ImportBatch).count() == 0
        assert db.query(ImportStagingRow).count() == 0


# ---------------------------------------------------------------------------
# 8. Unauthorized request and insufficient-permission request
# ---------------------------------------------------------------------------

def test_unauthorized_upload(import_env):
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=test.csv",
            content=ITEM_VALID_CSV,
        )
    assert response.status_code == 401


def test_insufficient_permission_upload(import_env):
    cashier = _create_user(
        import_env, role_code="CASHIER", permissions=()
    )
    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=test.csv",
            content=ITEM_VALID_CSV,
            headers={"Authorization": f"Bearer {cashier['token']}"},
        )
    assert response.status_code == 403


def test_unauthorized_preview(import_env):
    with TestClient(import_env.app) as client:
        response = client.get("/api/v1/import/preview/nonexistent")
    assert response.status_code == 401


def test_insufficient_permission_preview(import_env):
    cashier = _create_user(
        import_env, role_code="CASHIER", permissions=()
    )
    with TestClient(import_env.app) as client:
        response = client.get(
            "/api/v1/import/preview/nonexistent",
            headers={"Authorization": f"Bearer {cashier['token']}"},
        )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 9. Preview of existing batch with correct totals and bounded pagination
# ---------------------------------------------------------------------------

def test_preview_existing_batch(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        upload = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=mixed.csv",
            content=ITEM_MIXED_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    with TestClient(import_env.app) as client:
        preview = client.get(
            f"/api/v1/import/preview/{batch_id}",
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert preview.status_code == 200
    pv = preview.json()
    assert pv["batch_id"] == batch_id
    assert pv["import_type"] == "ITEM"
    assert pv["filename"] == "mixed.csv"
    assert pv["status"] == "PENDING_APPROVAL"
    assert pv["total_rows"] == 5
    assert pv["valid_rows"] == 3
    assert pv["invalid_rows"] == 2
    assert pv["uploaded_at"] is not None
    assert pv["uploaded_by"] == admin["user_id"]
    assert pv["pagination"]["limit"] == 50
    assert pv["pagination"]["offset"] == 0
    assert pv["pagination"]["total"] == 5


def test_preview_pagination_bounded(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        upload = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=paged.csv",
            content=ITEM_PAGINATED_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    with TestClient(import_env.app) as client:
        preview = client.get(
            f"/api/v1/import/preview/{batch_id}?limit=3&offset=0",
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert preview.status_code == 200
    pv = preview.json()
    assert pv["pagination"]["limit"] == 3
    assert pv["pagination"]["offset"] == 0
    assert len(pv["preview_data"]) == 3

    with TestClient(import_env.app) as client:
        preview2 = client.get(
            f"/api/v1/import/preview/{batch_id}?limit=3&offset=3",
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert preview2.status_code == 200
    pv2 = preview2.json()
    assert pv2["pagination"]["offset"] == 3
    assert len(pv2["preview_data"]) == 3

    with TestClient(import_env.app) as client:
        preview3 = client.get(
            f"/api/v1/import/preview/{batch_id}?limit=0&offset=0",
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert preview3.status_code == 200
    pv3 = preview3.json()
    assert len(pv3["preview_data"]) == 0


def test_preview_pagination_validation(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        upload = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=test.csv",
            content=ITEM_VALID_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
        batch_id = upload.json()["batch_id"]

        # limit too large
        r1 = client.get(
            f"/api/v1/import/preview/{batch_id}?limit=501",
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
        assert r1.status_code == 422

        # negative offset
        r2 = client.get(
            f"/api/v1/import/preview/{batch_id}?offset=-1",
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
        assert r2.status_code == 422


# ---------------------------------------------------------------------------
# 10. Preview of nonexistent batch
# ---------------------------------------------------------------------------

def test_preview_nonexistent_batch(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        response = client.get(
            "/api/v1/import/preview/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 11. Preview access denial (covered in section 8, also here for clarity)
# ---------------------------------------------------------------------------

def test_preview_cashier_denied(import_env):
    admin = _create_user(import_env)
    cashier = _create_user(
        import_env, role_code="CASHIER", permissions=()
    )
    with TestClient(import_env.app) as client:
        upload = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=test.csv",
            content=ITEM_VALID_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
        batch_id = upload.json()["batch_id"]

        response = client.get(
            f"/api/v1/import/preview/{batch_id}",
            headers={"Authorization": f"Bearer {cashier['token']}"},
        )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 12. Repeat upload creates distinct batches, no business mutation
# ---------------------------------------------------------------------------

def test_repeat_upload_creates_distinct_batches(import_env):
    admin = _create_user(import_env)
    with TestClient(import_env.app) as client:
        r1 = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=test.csv",
            content=ITEM_VALID_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
        r2 = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=test.csv",
            content=ITEM_VALID_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert r1.status_code == 200
    assert r2.status_code == 200
    bid1 = r1.json()["batch_id"]
    bid2 = r2.json()["batch_id"]
    assert bid1 != bid2

    with import_env.session_factory() as db:
        assert db.query(ImportBatch).filter(ImportBatch.id == uuid.UUID(bid1)).count() == 1
        assert db.query(ImportBatch).filter(ImportBatch.id == uuid.UUID(bid2)).count() == 1
        assert db.query(ImportBatch).filter(
            ImportBatch.uploaded_by == uuid.UUID(admin["user_id"])
        ).count() == 2


# ---------------------------------------------------------------------------
# 13. Endpoint does not create or update operational business records
# ---------------------------------------------------------------------------

def test_no_operational_records_created(import_env):
    admin = _create_user(import_env)
    with import_env.session_factory() as db:
        before = _count_business_records(db)

    with TestClient(import_env.app) as client:
        response = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=items.csv",
            content=ITEM_VALID_CSV,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
        assert response.status_code == 200
        batch_id = response.json()["batch_id"]

        preview = client.get(
            f"/api/v1/import/preview/{batch_id}",
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
        assert preview.status_code == 200
        pv = preview.json()
        assert pv["total_rows"] == 2
        assert pv["valid_rows"] == 2

    with import_env.session_factory() as db:
        after = _count_business_records(db)

    assert before == after, (
        f"Business records changed: before={before}, after={after}"
    )
    with import_env.session_factory() as db:
        assert db.query(ImportBatch).count() == 1


# ---------------------------------------------------------------------------
# Additional: preview invalid sample capped at MAX_INVALID_SAMPLE
# ---------------------------------------------------------------------------

def test_preview_invalid_sample_capped(import_env):
    admin = _create_user(import_env)
    header = b"ITEM CODE,DESCRIPTION,SALE PRICE\n"
    # 60 rows, all invalid (empty DESCRIPTION -> None -> fails str validation)
    rows = b"".join(
        f"LVT{i:04d},,100.0\n".encode() for i in range(1, 61)
    )
    csv_content = header + rows

    with TestClient(import_env.app) as client:
        upload = client.post(
            "/api/v1/import/upload?import_type=ITEM&filename=many.csv",
            content=csv_content,
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    with TestClient(import_env.app) as client:
        preview = client.get(
            f"/api/v1/import/preview/{batch_id}",
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    assert preview.status_code == 200
    pv = preview.json()
    assert pv["total_rows"] == 60
    assert pv["valid_rows"] == 0
    assert pv["invalid_rows"] == 60
    from app.api.routes.historical_import import MAX_INVALID_SAMPLE
    assert len(pv["invalid_details"]) == MAX_INVALID_SAMPLE
