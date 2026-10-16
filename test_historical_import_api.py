import pytest
import io
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_session_factory
from app.models.master import Permission, RolePermission, User, Role
from app.models.import_staging import ImportBatch, ImportStagingRow

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    database = get_session_factory()()
    yield database
    database.close()

@pytest.fixture(scope="module")
def admin_user(db):
    user = db.query(User).join(Role).filter(Role.code == 'ADMIN').first()
    perm = db.query(Permission).filter(Permission.code == "IMPORT_MANAGE").first()
    if not perm:
        perm = Permission(code="IMPORT_MANAGE", name="Manage Imports")
        db.add(perm)
        db.flush()
    
    role_perm = db.query(RolePermission).filter(
        RolePermission.role_id == user.role_id,
        RolePermission.permission_id == perm.id
    ).first()
    
    if not role_perm:
        db.add(RolePermission(role_id=user.role_id, permission_id=perm.id))
        db.commit()
    return user

@pytest.fixture(scope="module")
def admin_headers(db, admin_user):
    from app.api.deps import issue_session
    token, _ = issue_session(db, admin_user)
    db.commit()
    return {"Authorization": f"Bearer {token}"}

def test_upload_missing_import_type(admin_headers):
    file_content = b"COL1,COL2\nval1,val2"
    response = client.post("/api/v1/import/upload?filename=test.csv", content=file_content, headers=admin_headers)
    assert response.status_code == 422

def test_upload_invalid_import_type(admin_headers):
    file_content = b"COL1,COL2\nval1,val2"
    response = client.post("/api/v1/import/upload?import_type=UNKNOWN&filename=test.csv", content=file_content, headers=admin_headers)
    assert response.status_code == 400
    assert "Invalid import type" in response.json()["detail"]

def test_upload_unsupported_extension(admin_headers):
    file_content = b"text content"
    response = client.post("/api/v1/import/upload?import_type=ITEM&filename=test.txt", content=file_content, headers=admin_headers)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]
    
def test_upload_and_preview_valid_csv(admin_headers, db):
    csv_content = b"ITEM CODE,DESCRIPTION,SALE PRICE\nLVT001,Item 1,100.0\nLVT002,Item 2,200.0"
    response = client.post("/api/v1/import/upload?import_type=ITEM&filename=test.csv", content=csv_content, headers=admin_headers)
    assert response.status_code == 200
    batch_id = response.json()["batch_id"]
    
    preview_res = client.get(f"/api/v1/import/preview/{batch_id}", headers=admin_headers)
    assert preview_res.status_code == 200
    preview = preview_res.json()
    assert preview["total_rows"] == 2
    assert preview["valid_rows"] == 2
    assert preview["invalid_rows"] == 0

def test_upload_and_preview_invalid_rows(admin_headers, db):
    csv_content = b"ITEM CODE,SALE PRICE\nLVT001,100.0\nLVT002,200.0"
    response = client.post("/api/v1/import/upload?import_type=ITEM&filename=test.csv", content=csv_content, headers=admin_headers)
    assert response.status_code == 200
    batch_id = response.json()["batch_id"]
    
    preview_res = client.get(f"/api/v1/import/preview/{batch_id}", headers=admin_headers)
    assert preview_res.status_code == 200
    preview = preview_res.json()
    assert preview["total_rows"] == 2
    assert preview["valid_rows"] == 0
    assert preview["invalid_rows"] == 2

def test_preview_missing_batch(admin_headers):
    response = client.get("/api/v1/import/preview/nonexistent", headers=admin_headers)
    assert response.status_code == 404

def test_unauthorized_access():
    file_content = b"COL1,COL2\nval1,val2"
    response = client.post("/api/v1/import/upload?import_type=ITEM&filename=test.csv", content=file_content)
    assert response.status_code == 401
    
    response = client.get("/api/v1/import/preview/some_id")
    assert response.status_code == 401
