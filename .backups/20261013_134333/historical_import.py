from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import db_session, require_permission
from app.models.import_staging import ImportBatch, ImportStagingRow
from app.schemas.historical_import import (
    ImportItemRecord,
    ImportPurchaseRecord,
    ImportSaleRecord,
)
from app.models.master import User
from pydantic import ValidationError
import csv
import io
import uuid

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMPORT_ROWS = 50000
MAX_INVALID_SAMPLE = 50

SUPPORTED_IMPORT_TYPES = {"ITEM", "PURCHASE", "SALE"}

SCHEMA_MAP = {
    "ITEM": ImportItemRecord,
    "PURCHASE": ImportPurchaseRecord,
    "SALE": ImportSaleRecord,
}

router = APIRouter(prefix="/import", tags=["historical_import"])


def _format_validation_error(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(loc_part) for loc_part in err.get("loc", ())) or "row"
        msg = err.get("msg", "Invalid value")
        parts.append(f"{loc}: {msg}")
    return "; ".join(parts) if parts else "Validation failed"


@router.post("/upload")
async def upload_historical_import(
    request: Request,
    filename: str = Query(..., min_length=1, max_length=255),
    import_type: str = Query(...),
    user: User = Depends(require_permission('IMPORT_MANAGE')),
    db: Session = Depends(db_session),
):
    if import_type not in SCHEMA_MAP:
        raise HTTPException(
            status_code=400,
            detail="Invalid import type. Must be ITEM, PURCHASE, or SALE.",
        )

    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Only CSV files are supported.",
        )

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            parsed_size = int(content_length)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid Content-Length header."
            )
        if parsed_size == 0:
            raise HTTPException(status_code=400, detail="File is empty.")
        if parsed_size > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024 * 1024)}MB.",
            )

    contents = await request.body()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024 * 1024)}MB.",
        )
    if not contents:
        raise HTTPException(status_code=400, detail="File is empty.")

    try:
        text_content = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File must be valid UTF-8 encoded CSV.",
        )

    try:
        reader = csv.DictReader(io.StringIO(text_content))
    except csv.Error:
        raise HTTPException(status_code=400, detail="Malformed CSV file.")

    fieldnames = reader.fieldnames
    if not fieldnames:
        raise HTTPException(
            status_code=400,
            detail="Spreadsheet is empty or malformed.",
        )

    seen: dict[str, int] = {}
    duplicates: list[str] = []
    for col in fieldnames:
        normalized = col.strip()
        if normalized in seen:
            if normalized not in duplicates:
                duplicates.append(normalized)
        seen[normalized] = seen.get(normalized, 0) + 1
    if duplicates:
        raise HTTPException(
            status_code=400,
            detail="Duplicate or colliding headers detected: "
            + ", ".join(sorted(duplicates)),
        )

    try:
        raw_rows = list(reader)
    except csv.Error:
        raise HTTPException(status_code=400, detail="Malformed CSV file.")

    if not raw_rows:
        raise HTTPException(
            status_code=400,
            detail="File has no data rows.",
        )

    if len(raw_rows) > MAX_IMPORT_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"Too many rows. Maximum is {MAX_IMPORT_ROWS}.",
        )

    schema = SCHEMA_MAP[import_type]

    try:
        batch = ImportBatch(
            branch_id=user.branch_id,
            filename=filename,
            uploaded_by=user.id,
            status="PENDING_APPROVAL",
        )
        db.add(batch)
        db.flush()

        for idx, row in enumerate(raw_rows):
            row_number = idx + 2
            val_status = "VALID"
            err_detail = None

            clean_row = {
                k: (v if str(v).strip() != "" else None)
                for k, v in row.items()
                if k is not None
            }

            try:
                schema.model_validate(clean_row)
            except ValidationError as e:
                val_status = "INVALID"
                err_detail = _format_validation_error(e)
            except Exception:
                val_status = "INVALID"
                err_detail = "Validation failed"

            staging_row = ImportStagingRow(
                batch_id=batch.id,
                row_number=row_number,
                row_type=import_type,
                raw_data=clean_row,
                validation_status=val_status,
                error_details=err_detail,
            )
            db.add(staging_row)

        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Internal server error during upload staging.",
        )

    valid_count = db.query(ImportStagingRow).filter(
        ImportStagingRow.batch_id == batch.id,
        ImportStagingRow.validation_status == "VALID",
    ).count()
    invalid_count = db.query(ImportStagingRow).filter(
        ImportStagingRow.batch_id == batch.id,
        ImportStagingRow.validation_status == "INVALID",
    ).count()

    return {
        "batch_id": str(batch.id),
        "total_rows": len(raw_rows),
        "valid_rows": valid_count,
        "invalid_rows": invalid_count,
        "message": f"Successfully uploaded and staged {len(raw_rows)} rows.",
    }


@router.get("/preview/{batch_id}")
def preview_historical_import(
    batch_id: str,
    limit: int = Query(50, ge=0, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission('IMPORT_MANAGE')),
    db: Session = Depends(db_session),
):
    try:
        batch_uuid = uuid.UUID(batch_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import batch not found.",
        )
    batch = db.query(ImportBatch).filter(ImportBatch.id == batch_uuid).first()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import batch not found.",
        )

    rows_query = db.query(ImportStagingRow).filter(
        ImportStagingRow.batch_id == batch_uuid
    )

    total_rows = rows_query.count()
    valid_rows = rows_query.filter(
        ImportStagingRow.validation_status == "VALID"
    ).count()
    invalid_rows = rows_query.filter(
        ImportStagingRow.validation_status == "INVALID"
    ).count()

    invalid_sample = (
        rows_query.filter(ImportStagingRow.validation_status == "INVALID")
        .order_by(ImportStagingRow.row_number)
        .limit(MAX_INVALID_SAMPLE)
        .all()
    )
    invalid_details = [
        {"row_number": r.row_number, "error": r.error_details} for r in invalid_sample
    ]

    sample_rows = (
        rows_query.order_by(ImportStagingRow.row_number)
        .offset(offset)
        .limit(limit)
        .all()
    )
    preview_data = [
        {
            "row_number": r.row_number,
            "row_type": r.row_type,
            "status": r.validation_status,
            "raw_data": r.raw_data,
            "error": r.error_details,
        }
        for r in sample_rows
    ]

    import_type = db.scalar(
        select(ImportStagingRow.row_type)
        .where(ImportStagingRow.batch_id == batch_uuid)
        .limit(1)
    )

    return {
        "batch_id": str(batch.id),
        "import_type": import_type,
        "filename": batch.filename,
        "status": batch.status,
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "invalid_details": invalid_details,
        "uploaded_at": batch.uploaded_at.isoformat() if batch.uploaded_at else None,
        "uploaded_by": str(batch.uploaded_by) if batch.uploaded_by else None,
        "preview_data": preview_data,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total_rows,
        },
    }
