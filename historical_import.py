from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
    request: Request,
    filename: str = Query(...),
    import_type: str = Query(...),
    user: User = Depends(require_permission('IMPORT_MANAGE')),
    db: Session = Depends(db_session)
):
    if import_type not in ["ITEM", "PURCHASE", "SALE"]:
        raise HTTPException(status_code=400, detail="Invalid import type. Must be ITEM, PURCHASE, or SALE.")
        
    if not filename.lower().endswith('.csv'):
         raise HTTPException(status_code=400, detail="Unsupported file format. Please upload a CSV file.")
    
    try:
        contents = await request.body()
        text_content = contents.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text_content))
        raw_rows = list(reader)
    except Exception as e:
         raise HTTPException(status_code=400, detail=f"Failed to read CSV: {str(e)}")

    if not raw_rows:
         raise HTTPException(status_code=400, detail="Spreadsheet is empty or malformed.")
         
    batch = ImportBatch(
        branch_id=user.branch_id,
        filename=filename,
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
