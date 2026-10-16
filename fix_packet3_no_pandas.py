import os
import subprocess
import json
import re
from datetime import datetime

root = r"C:\Lovely Tech POS"
backend_dir = os.path.join(root, "backend")

routes_file = os.path.join(backend_dir, "app", "api", "routes", "historical_import.py")
test_file = os.path.join(backend_dir, "tests", "test_historical_import_api.py")
timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

# Rewrite routes without pandas
route_code = """from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.api.deps import db_session, require_permission
from app.models.import_staging import ImportBatch, ImportStagingRow
from app.schemas.historical_import import ImportItemRecord, ImportPurchaseRecord, ImportSaleRecord
from app.models.master import User
import csv
import io

router = APIRouter(prefix="/import", tags=["historical_import"])

@router.post("/upload")
async def upload_historical_import(
    file: UploadFile = File(...),
    import_type: str = Form(...),
    user: User = Depends(require_permission('IMPORT_MANAGE')),
    db: Session = Depends(db_session)
):
    if import_type not in ["ITEM", "PURCHASE", "SALE"]:
        raise HTTPException(status_code=400, detail="Invalid import type. Must be ITEM, PURCHASE, or SALE.")
        
    if not file.filename.lower().endswith('.csv'):
         raise HTTPException(status_code=400, detail="Unsupported file format. Please upload a CSV file. (Excel dependencies not installed)")
    
    try:
        contents = await file.read()
        text_content = contents.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text_content))
        raw_rows = list(reader)
    except Exception as e:
         raise HTTPException(status_code=400, detail=f"Failed to read CSV: {str(e)}")

    if not raw_rows:
         raise HTTPException(status_code=400, detail="Spreadsheet is empty or malformed.")
         
    batch = ImportBatch(
        branch_id=user.branch_id,
        filename=file.filename,
        uploaded_by=user.id,
        status="PENDING_APPROVAL"
    )
    db.add(batch)
    db.flush()
    
    schema_map = {
        "ITEM": ImportItemRecord,
        "PURCHASE": ImportPurchaseRecord,
        "SALE": ImportSaleRecord
    }
    schema = schema_map[import_type]
    
    for idx, row in enumerate(raw_rows):
        row_number = idx + 2 # Assuming header is row 1
        val_status = "VALID"
        err_detail = None
        
        # Clean empty strings to None to help Pydantic
        clean_row = {k: (v if str(v).strip() != "" else None) for k, v in row.items() if k is not None}
        
        try:
             schema.model_validate(clean_row)
        except Exception as e:
             val_status = "INVALID"
             err_detail = str(e)
             
        staging_row = ImportStagingRow(
            batch_id=batch.id,
            row_number=row_number,
            row_type=import_type,
            raw_data=clean_row,
            validation_status=val_status,
            error_details=err_detail
        )
        db.add(staging_row)
        
    db.commit()
    
    return {
        "batch_id": batch.id,
        "message": f"Successfully uploaded and staged {len(raw_rows)} rows."
    }

@router.get("/preview/{batch_id}")
def preview_historical_import(
    batch_id: str,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(require_permission('IMPORT_MANAGE')),
    db: Session = Depends(db_session)
):
    batch = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found.")
        
    rows_query = db.query(ImportStagingRow).filter(ImportStagingRow.batch_id == batch_id)
    
    total_rows = rows_query.count()
    valid_rows = rows_query.filter(ImportStagingRow.validation_status == "VALID").count()
    invalid_rows = rows_query.filter(ImportStagingRow.validation_status == "INVALID").count()
    
    invalid_sample = rows_query.filter(ImportStagingRow.validation_status == "INVALID").limit(5).all()
    invalid_details = [{"row_number": r.row_number, "error": r.error_details} for r in invalid_sample]
    
    sample_rows = rows_query.offset(offset).limit(limit).all()
    preview_data = [{
        "row_number": r.row_number,
        "status": r.validation_status,
        "raw_data": r.raw_data,
        "error": r.error_details
    } for r in sample_rows]
    
    return {
        "batch_id": batch.id,
        "filename": batch.filename,
        "status": batch.status,
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "invalid_sample": invalid_details,
        "preview_data": preview_data
    }
"""

# Rewrite tests without pandas
test_code = """import pytest
import io
from app.models.import_staging import ImportBatch, ImportStagingRow
from app.models.master import Permission, RolePermission

@pytest.fixture(autouse=True)
def setup_import_permission(db, admin_user):
    perm = db.query(Permission).filter(Permission.code == "IMPORT_MANAGE").first()
    if not perm:
        perm = Permission(code="IMPORT_MANAGE", name="Manage Imports")
        db.add(perm)
        db.flush()
    
    role_perm = db.query(RolePermission).filter(
        RolePermission.role_id == admin_user.role_id,
        RolePermission.permission_id == perm.id
    ).first()
    
    if not role_perm:
        db.add(RolePermission(role_id=admin_user.role_id, permission_id=perm.id))
        db.commit()

def test_upload_missing_import_type(client, admin_headers):
    file_content = b"COL1,COL2\\nval1,val2"
    files = {"file": ("test.csv", io.BytesIO(file_content), "text/csv")}
    response = client.post("/api/v1/import/upload", files=files, headers=admin_headers)
    assert response.status_code == 422

def test_upload_invalid_import_type(client, admin_headers):
    file_content = b"COL1,COL2\\nval1,val2"
    files = {"file": ("test.csv", io.BytesIO(file_content), "text/csv")}
    data = {"import_type": "UNKNOWN"}
    response = client.post("/api/v1/import/upload", files=files, data=data, headers=admin_headers)
    assert response.status_code == 400
    assert "Invalid import type" in response.json()["detail"]

def test_upload_unsupported_extension(client, admin_headers):
    file_content = b"text content"
    files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
    data = {"import_type": "ITEM"}
    response = client.post("/api/v1/import/upload", files=files, data=data, headers=admin_headers)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]
    
def test_upload_and_preview_valid_csv(client, admin_headers, db):
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

def test_upload_and_preview_invalid_rows(client, admin_headers, db):
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

def test_preview_missing_batch(client, admin_headers):
    response = client.get("/api/v1/import/preview/nonexistent", headers=admin_headers)
    assert response.status_code == 404

def test_unauthorized_access(client):
    file_content = b"COL1,COL2\\nval1,val2"
    files = {"file": ("test.csv", io.BytesIO(file_content), "text/csv")}
    data = {"import_type": "ITEM"}
    response = client.post("/api/v1/import/upload", files=files, data=data)
    assert response.status_code == 401
    
    response = client.get("/api/v1/import/preview/some_id")
    assert response.status_code == 401
"""

with open(routes_file, "w", encoding="utf-8") as f:
    f.write(route_code)

with open(test_file, "w", encoding="utf-8") as f:
    f.write(test_code)

print("Files updated successfully (Removed pandas dependencies). Running tests...\n")

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