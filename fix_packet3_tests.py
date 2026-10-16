import os
import subprocess
import json
import re
from datetime import datetime

root = r"C:\Lovely Tech POS"
backend_dir = os.path.join(root, "backend")
test_file = os.path.join(backend_dir, "tests", "test_historical_import_api.py")
timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

test_code = """import pytest
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
    # Ensure IMPORT_MANAGE permission exists
    perm = db.query(Permission).filter(Permission.code == "IMPORT_MANAGE").first()
    if not perm:
        perm = Permission(code="IMPORT_MANAGE", name="Manage Imports")
        db.add(perm)
        db.flush()
    
    # Assign permission to Admin role
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
    file_content = b"COL1,COL2\\nval1,val2"
    files = {"file": ("test.csv", io.BytesIO(file_content), "text/csv")}
    response = client.post("/api/v1/import/upload", files=files, headers=admin_headers)
    assert response.status_code == 422

def test_upload_invalid_import_type(admin_headers):
    file_content = b"COL1,COL2\\nval1,val2"
    files = {"file": ("test.csv", io.BytesIO(file_content), "text/csv")}
    data = {"import_type": "UNKNOWN"}
    response = client.post("/api/v1/import/upload", files=files, data=data, headers=admin_headers)
    assert response.status_code == 400
    assert "Invalid import type" in response.json()["detail"]

def test_upload_unsupported_extension(admin_headers):
    file_content = b"text content"
    files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
    data = {"import_type": "ITEM"}
    response = client.post("/api/v1/import/upload", files=files, data=data, headers=admin_headers)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]
    
def test_upload_and_preview_valid_csv(admin_headers, db):
    csv_content = b"ITEM CODE,DESCRIPTION,SALE PRICE\\nLVT001,Item 1,100.0\\nLVT002,Item 2,200.0"
    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    data = {"import_type": "ITEM"}
    
    response = client.post("/api/v1/import/upload", files=files, data=data, headers=admin_headers)
    assert response.status_code == 200
    batch_id = response.json()["batch_id"]
    
    preview_res = client.get(f"/api/v1/import/preview/{batch_id}", headers=admin_headers)
    assert preview_res.status_code == 200
    preview = preview_res.json()
    assert preview["total_rows"] == 2
    assert preview["valid_rows"] == 2
    assert preview["invalid_rows"] == 0

def test_upload_and_preview_invalid_rows(admin_headers, db):
    # Missing DESCRIPTION
    csv_content = b"ITEM CODE,SALE PRICE\\nLVT001,100.0\\nLVT002,200.0"
    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    data = {"import_type": "ITEM"}
    
    response = client.post("/api/v1/import/upload", files=files, data=data, headers=admin_headers)
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
    file_content = b"COL1,COL2\\nval1,val2"
    files = {"file": ("test.csv", io.BytesIO(file_content), "text/csv")}
    data = {"import_type": "ITEM"}
    response = client.post("/api/v1/import/upload", files=files, data=data)
    assert response.status_code == 401
    
    response = client.get("/api/v1/import/preview/some_id")
    assert response.status_code == 401
"""

with open(test_file, "w", encoding="utf-8") as f:
    f.write(test_code)

print("Test fixtures fixed. Running tests...\n")

pytest_exe = os.path.join(backend_dir, ".venv", "Scripts", "pytest.exe")
if not os.path.exists(pytest_exe): pytest_exe = "pytest"

env = os.environ.copy()
env["PYTHONPATH"] = backend_dir
res = subprocess.run([pytest_exe, "-v", "tests/test_historical_import_api.py"], cwd=backend_dir, capture_output=True, text=True, env=env)
print(res.stdout)
if res.stderr:
    print(res.stderr)

if res.returncode == 0:
    print("\n========== UPDATING DASHBOARD ==========")
    s_json = os.path.join(root, "docs", "project-status.json")
    s_html = os.path.join(root, "docs", "project-dashboard.html")
    
    with open(s_json, 'r', encoding='utf-8') as f:
        d = json.load(f)
    for task in d.get("tasks", []):
        if task.get("id") == "T-004":
            task["status"] = "IN PROGRESS"
            task["evidence"] = "Packet 1 (Schemas), Packet 2 (Staging Models), and Packet 3 (Backend Upload/Preview API) implemented and tested. Support limited to CSV uploads due to missing openpyxl/pandas dependencies."
    
    j_str = json.dumps(d, indent=4)
    with open(s_json, 'w', encoding='utf-8') as f: f.write(j_str)
    
    try:
        with open(s_html, 'r', encoding='utf-8') as f: h_data = f.read()
        h_new = re.sub(r'(<script\s+id="project-data"\s+type="application/json">).*?(</script>)', lambda m: f"{m.group(1)}\n{j_str}\n{m.group(2)}", h_data, flags=re.DOTALL)
        with open(s_html, 'w', encoding='utf-8') as f: f.write(h_new)
    except: pass
    print("Dashboard updated successfully. T-004 status set to IN PROGRESS.")