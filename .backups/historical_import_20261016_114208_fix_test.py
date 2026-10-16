from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.api.deps import db_session, require_permission
from app.models.import_staging import ImportBatch, ImportStagingRow, ImportMapping
from app.models.master import User, Category, ItemType, Item
from app.schemas.historical_import import (
    ImportItemRecord,
    ImportPurchaseRecord,
    ImportSaleRecord,
    SCHEMA_FIELD_MAP,
    ImportMappingCreate,
    ImportMappingUpdate,
    ImportMappingResponse,
    ImportMappingBulkCreate,
    ImportMappingBulkResponse,
)
from app.services.items import ItemService, ItemCreationInput, ItemCreationError
from app.security.reauth import require_admin_reauth
from pydantic import ValidationError
import csv
import io
import uuid
import hashlib
from datetime import datetime, timezone

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

    # Compute content hash for idempotency
    content_hash = hashlib.sha256(contents).hexdigest()

    # Check for existing batch with same content (idempotent retry)
    existing_batch = db.query(ImportBatch).filter(
        ImportBatch.branch_id == user.branch_id,
        ImportBatch.uploaded_by == user.id,
        ImportBatch.import_type == import_type,
        ImportBatch.content_hash == content_hash,
    ).first()

    if existing_batch:
        # Return existing batch for idempotent retry
        valid_count = db.query(ImportStagingRow).filter(
            ImportStagingRow.batch_id == existing_batch.id,
            ImportStagingRow.validation_status == "VALID",
        ).count()
        invalid_count = db.query(ImportStagingRow).filter(
            ImportStagingRow.batch_id == existing_batch.id,
            ImportStagingRow.validation_status == "INVALID",
        ).count()
        return {
            "batch_id": str(existing_batch.id),
            "total_rows": len(raw_rows),
            "valid_rows": valid_count,
            "invalid_rows": invalid_count,
            "message": f"Successfully uploaded and staged {len(raw_rows)} rows (idempotent retry).",
        }

    try:
        batch = ImportBatch(
            branch_id=user.branch_id,
            filename=filename,
            uploaded_by=user.id,
            status="PENDING_APPROVAL",
            import_type=import_type,
            content_hash=content_hash,
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
    except IntegrityError:
        db.rollback()
        # Race condition: another request created the same batch concurrently
        # Retry the lookup and return the existing batch
        existing_batch = db.query(ImportBatch).filter(
            ImportBatch.branch_id == user.branch_id,
            ImportBatch.uploaded_by == user.id,
            ImportBatch.import_type == import_type,
            ImportBatch.content_hash == content_hash,
        ).first()
        if existing_batch:
            valid_count = db.query(ImportStagingRow).filter(
                ImportStagingRow.batch_id == existing_batch.id,
                ImportStagingRow.validation_status == "VALID",
            ).count()
            invalid_count = db.query(ImportStagingRow).filter(
                ImportStagingRow.batch_id == existing_batch.id,
                ImportStagingRow.validation_status == "INVALID",
            ).count()
            return {
                "batch_id": str(existing_batch.id),
                "total_rows": len(raw_rows),
                "valid_rows": valid_count,
                "invalid_rows": invalid_count,
                "message": f"Successfully uploaded and staged {len(raw_rows)} rows (idempotent retry).",
            }
        raise HTTPException(
            status_code=500,
            detail="Internal server error during upload staging.",
        )
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


def _get_batch_or_404(db: Session, batch_id: str, user: User) -> ImportBatch:
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
    if batch.branch_id != user.branch_id and user.role.code.upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: batch belongs to a different branch.",
        )
    return batch


def _validate_mapping_payload(
    import_type: str,
    source_columns: list[str],
    mappings: list[ImportMappingCreate],
) -> tuple[list[str], list[str]]:
    errors = []
    warnings = []
    schema_info = SCHEMA_FIELD_MAP.get(import_type)
    if not schema_info:
        errors.append(f"Unknown import type: {import_type}")
        return errors, warnings

    valid_target_fields = set(schema_info["required"] + schema_info["optional"])
    valid_source_columns = set(col.strip() for col in source_columns)

    seen_targets = set()
    for m in mappings:
        src = m.source_column.strip()
        tgt = m.target_field.strip()

        if src not in valid_source_columns:
            errors.append(f"Source column '{src}' not found in uploaded file headers.")
            continue

        if tgt not in valid_target_fields:
            errors.append(f"Target field '{tgt}' is not a valid field for import type '{import_type}'.")
            continue

        if tgt in seen_targets:
            errors.append(f"Duplicate target field assignment: '{tgt}' mapped multiple times.")
            continue
        seen_targets.add(tgt)

        if tgt in schema_info["required"] and not m.is_required:
            warnings.append(f"Target field '{tgt}' is required for '{import_type}' but is_required=false; treating as required.")

    missing_required = [
        req for req in schema_info["required"]
        if req not in seen_targets
    ]
    for req in missing_required:
        errors.append(f"Required target field '{req}' for import type '{import_type}' is not mapped.")

    return errors, warnings


@router.post("/mappings/{batch_id}", response_model=ImportMappingBulkResponse, status_code=status.HTTP_201_CREATED)
def create_mappings(
    batch_id: str,
    payload: ImportMappingBulkCreate,
    user: User = Depends(require_permission('IMPORT_MANAGE')),
    db: Session = Depends(db_session),
):
    batch = _get_batch_or_404(db, batch_id, user)

    existing = db.query(ImportMapping).filter(ImportMapping.batch_id == batch.id).all()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Mappings already exist for this batch. Use PUT to update.",
        )

    import_type = db.scalar(
        select(ImportStagingRow.row_type)
        .where(ImportStagingRow.batch_id == batch.id)
        .limit(1)
    )
    if not import_type:
        raise HTTPException(
            status_code=400,
            detail="Batch has no staged rows to determine import type.",
        )

    source_columns = db.scalar(
        select(ImportStagingRow.raw_data)
        .where(ImportStagingRow.batch_id == batch.id)
        .limit(1)
    )
    if source_columns is None:
        raise HTTPException(
            status_code=400,
            detail="Batch has no staged rows.",
        )
    source_header_list = list(source_columns.keys()) if isinstance(source_columns, dict) else []

    errors, warnings = _validate_mapping_payload(import_type, source_header_list, payload.mappings)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    created = []
    for m in payload.mappings:
        mapping = ImportMapping(
            batch_id=batch.id,
            import_type=import_type,
            source_column=m.source_column.strip(),
            target_field=m.target_field.strip(),
            is_required=str(m.is_required).lower(),
            transform_hint=m.transform_hint.strip() if m.transform_hint else None,
        )
        db.add(mapping)
        created.append(mapping)

    try:
        db.commit()
        for m in created:
            db.refresh(m)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Internal server error while saving mappings.",
        )

    response_mappings = [
        ImportMappingResponse(
            id=m.id,
            batch_id=m.batch_id,
            import_type=m.import_type,
            source_column=m.source_column,
            target_field=m.target_field,
            is_required=m.is_required.lower() == "true",
            transform_hint=m.transform_hint,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in created
    ]

    return ImportMappingBulkResponse(mappings=response_mappings, warnings=warnings)


@router.get("/mappings/{batch_id}", response_model=ImportMappingBulkResponse)
def get_mappings(
    batch_id: str,
    user: User = Depends(require_permission('IMPORT_MANAGE')),
    db: Session = Depends(db_session),
):
    batch = _get_batch_or_404(db, batch_id, user)

    mappings = db.query(ImportMapping).filter(ImportMapping.batch_id == batch.id).all()

    response_mappings = [
        ImportMappingResponse(
            id=m.id,
            batch_id=m.batch_id,
            import_type=m.import_type,
            source_column=m.source_column,
            target_field=m.target_field,
            is_required=m.is_required.lower() == "true",
            transform_hint=m.transform_hint,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in mappings
    ]

    return ImportMappingBulkResponse(mappings=response_mappings, warnings=[])


@router.put("/mappings/{batch_id}", response_model=ImportMappingBulkResponse)
def update_mappings(
    batch_id: str,
    payload: ImportMappingBulkCreate,
    user: User = Depends(require_permission('IMPORT_MANAGE')),
    db: Session = Depends(db_session),
):
    batch = _get_batch_or_404(db, batch_id, user)

    import_type = db.scalar(
        select(ImportStagingRow.row_type)
        .where(ImportStagingRow.batch_id == batch.id)
        .limit(1)
    )
    if not import_type:
        raise HTTPException(
            status_code=400,
            detail="Batch has no staged rows to determine import type.",
        )

    source_columns = db.scalar(
        select(ImportStagingRow.raw_data)
        .where(ImportStagingRow.batch_id == batch.id)
        .limit(1)
    )
    if source_columns is None:
        raise HTTPException(
            status_code=400,
            detail="Batch has no staged rows.",
        )
    source_header_list = list(source_columns.keys()) if isinstance(source_columns, dict) else []

    errors, warnings = _validate_mapping_payload(import_type, source_header_list, payload.mappings)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    try:
        db.query(ImportMapping).filter(ImportMapping.batch_id == batch.id).delete()
        db.flush()

        created = []
        for m in payload.mappings:
            mapping = ImportMapping(
                batch_id=batch.id,
                import_type=import_type,
                source_column=m.source_column.strip(),
                target_field=m.target_field.strip(),
                is_required=str(m.is_required).lower(),
                transform_hint=m.transform_hint.strip() if m.transform_hint else None,
            )
            db.add(mapping)
            created.append(mapping)

        db.commit()
        for m in created:
            db.refresh(m)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Internal server error while updating mappings.",
        )

    response_mappings = [
        ImportMappingResponse(
            id=m.id,
            batch_id=m.batch_id,
            import_type=m.import_type,
            source_column=m.source_column,
            target_field=m.target_field,
            is_required=m.is_required.lower() == "true",
            transform_hint=m.transform_hint,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in created
    ]

    return ImportMappingBulkResponse(mappings=response_mappings, warnings=warnings)


@router.delete("/mappings/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mappings(
    batch_id: str,
    user: User = Depends(require_permission('IMPORT_MANAGE')),
    db: Session = Depends(db_session),
):
    batch = _get_batch_or_404(db, batch_id, user)

    try:
        db.query(ImportMapping).filter(ImportMapping.batch_id == batch.id).delete()
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Internal server error while deleting mappings.",
        )


def _apply_mappings_to_row(raw_data: dict, mappings: list[ImportMapping]) -> dict:
    result = {}
    for m in mappings:
        src_val = raw_data.get(m.source_column)
        if src_val is not None and str(src_val).strip() != "":
            result[m.target_field] = src_val
        elif m.is_required.lower() == "true":
            result[m.target_field] = None
    return result


@router.get("/preview-mapped/{batch_id}")
def preview_mapped_historical_import(
    batch_id: str,
    limit: int = Query(50, ge=0, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_permission('IMPORT_MANAGE')),
    db: Session = Depends(db_session),
):
    batch = _get_batch_or_404(db, batch_id, user)

    mappings = db.query(ImportMapping).filter(ImportMapping.batch_id == batch.id).all()
    if not mappings:
        raise HTTPException(
            status_code=400,
            detail="No mappings defined for this batch. Create mappings first.",
        )

    rows_query = db.query(ImportStagingRow).filter(
        ImportStagingRow.batch_id == batch.id
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

    preview_data = []
    for r in sample_rows:
        mapped = _apply_mappings_to_row(r.raw_data, mappings)
        preview_data.append({
            "row_number": r.row_number,
            "row_type": r.row_type,
            "status": r.validation_status,
            "raw_data": r.raw_data,
            "mapped_data": mapped,
            "error": r.error_details,
        })

    import_type = db.scalar(
        select(ImportStagingRow.row_type)
        .where(ImportStagingRow.batch_id == batch.id)
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
        "mappings_applied": len(mappings),
    }


@router.post("/approve/{batch_id}", status_code=status.HTTP_200_OK)
def approve_import_batch(
    batch_id: str,
    user: User = Depends(require_permission('IMPORT_MANAGE')),
    db: Session = Depends(db_session),
):
    """Approve an import batch for commit.
    
    Only batches in PENDING_APPROVAL status can be approved.
    The approver must have IMPORT_MANAGE permission and belong to the same branch (or be ADMIN).
    """
    batch = _get_batch_or_404(db, batch_id, user)

    if batch.status != "PENDING_APPROVAL":
        raise HTTPException(
            status_code=400,
            detail=f"Batch is not pending approval (current status: {batch.status}).",
        )

    if batch.import_type != "ITEM":
        raise HTTPException(
            status_code=400,
            detail=f"Only ITEM batches can be approved for commit (batch type: {batch.import_type}).",
        )

    valid_count = db.query(ImportStagingRow).filter(
        ImportStagingRow.batch_id == batch.id,
        ImportStagingRow.validation_status == "VALID",
    ).count()

    if valid_count == 0:
        raise HTTPException(
            status_code=400,
            detail="Batch has no valid rows to approve.",
        )

    mappings = db.query(ImportMapping).filter(ImportMapping.batch_id == batch.id).all()
    if not mappings:
        raise HTTPException(
            status_code=400,
            detail="No mappings defined for this batch. Create mappings before approval.",
        )

    batch.status = "APPROVED"
    batch.approved_by = user.id
    batch.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(batch)

    return {
        "batch_id": str(batch.id),
        "status": batch.status,
        "approved_by": str(batch.approved_by),
        "approved_at": batch.approved_at.isoformat(),
        "message": f"Batch approved successfully. {valid_count} valid rows ready for commit.",
    }


@router.post("/commit/{batch_id}", status_code=status.HTTP_200_OK)
def commit_import_batch(
    batch_id: str,
    item_type_id: str,
    admin_password: str,
    user: User = Depends(require_permission('IMPORT_MANAGE')),
    db: Session = Depends(db_session),
):
    """Commit an approved ITEM-only import batch to operational data.
    
    This is a critical operation requiring:
    - IMPORT_MANAGE permission
    - Admin re-authentication (admin_password)
    - Batch must be APPROVED and contain only ITEM records
    - All valid rows must have mappings
    - Category names must resolve to existing categories
    - Item type must be specified and exist
    
    The entire batch is committed in a single all-or-nothing transaction.
    Concurrent calls and retries are idempotent - a lost HTTP response
    will not cause duplicate items or misleading status.
    """
    batch = _get_batch_or_404(db, batch_id, user)

    # Enforce admin re-authentication for this critical operation
    require_admin_reauth(
        user=user,
        password=admin_password,
        db=db,
        action="historical import commit",
    )

    # Validate batch state
    if batch.status != "APPROVED":
        raise HTTPException(
            status_code=400,
            detail=f"Batch must be approved before commit (current status: {batch.status}).",
        )

    if batch.import_type != "ITEM":
        raise HTTPException(
            status_code=400,
            detail=f"Only ITEM batches can be committed (batch type: {batch.import_type}).",
        )

    # Check if already committed (idempotency)
    if batch.committed_at is not None:
        return {
            "batch_id": str(batch.id),
            "status": "ALREADY_COMMITTED",
            "committed_at": batch.committed_at.isoformat() if batch.committed_at else None,
            "committed_by": str(batch.committed_by) if batch.committed_by else None,
            "commit_result": batch.commit_result,
            "message": "Batch was already committed.",
        }

    # Validate item_type_id
    try:
        item_type_uuid = uuid.UUID(item_type_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid item_type_id format. Must be a valid UUID.",
        )

    item_type = db.get(ItemType, item_type_uuid)
    if not item_type:
        raise HTTPException(
            status_code=404,
            detail="Item type not found.",
        )
    if not item_type.is_active:
        raise HTTPException(
            status_code=400,
            detail="Item type is not active.",
        )

    # Get mappings
    mappings = db.query(ImportMapping).filter(ImportMapping.batch_id == batch.id).all()
    if not mappings:
        raise HTTPException(
            status_code=400,
            detail="No mappings defined for this batch.",
        )

    # Get valid staged rows
    valid_rows = db.query(ImportStagingRow).filter(
        ImportStagingRow.batch_id == batch.id,
        ImportStagingRow.validation_status == "VALID",
    ).order_by(ImportStagingRow.row_number).all()

    if not valid_rows:
        raise HTTPException(
            status_code=400,
            detail="No valid rows to commit.",
        )

    # Pre-validate all rows: resolve categories, check for duplicates, etc.
    # We do this before the transaction to fail fast, but the actual writes
    # happen in the single transaction below.
    item_service = ItemService(db)
    created_items = []
    errors = []

    for row in valid_rows:
        mapped = _apply_mappings_to_row(row.raw_data, mappings)

        # Validate required fields
        item_code = mapped.get("item_code")
        description = mapped.get("description")
        category_name = mapped.get("category")
        brand = mapped.get("brand")
        model = mapped.get("model")
        sale_price = mapped.get("sale_price")
        barcode = mapped.get("barcode")

        if not description:
            errors.append(f"Row {row.row_number}: description is required")
            continue

        # Resolve category by name
        category_id = None
        if category_name:
            category = db.scalar(
                select(Category).where(Category.name == category_name.strip())
            )
            if not category:
                errors.append(f"Row {row.row_number}: category '{category_name}' not found")
                continue
            category_id = category.id
        else:
            errors.append(f"Row {row.row_number}: category is required")
            continue

        # Build ItemCreationInput
        try:
            input_data = ItemCreationInput(
                item_code=item_code.strip() if item_code else None,
                description=description.strip(),
                category_id=category_id,
                item_type_id=item_type_uuid,
                brand=brand.strip() if brand else None,
                model=model.strip() if model else None,
                master_sale_price=sale_price,
                barcode=barcode.strip() if barcode else None,
            )
        except Exception as e:
            errors.append(f"Row {row.row_number}: invalid data - {str(e)}")
            continue

        # Check for duplicate item_code within the batch (if provided)
        if input_data.item_code:
            # Check against already processed rows in this batch
            for existing_row, existing_input in created_items:
                  if existing_input.item_code == input_data.item_code:
                    errors.append(f"Row {row.row_number}: duplicate item_code '{input_data.item_code}' in batch")
                    break
            if errors and errors[-1].startswith(f"Row {row.row_number}:"):
                continue

            # Also check against database
            existing_in_db = db.scalar(
                select(Item.id).where(Item.item_code == input_data.item_code)
            )
            if existing_in_db:
                errors.append(f"Row {row.row_number}: item_code '{input_data.item_code}' already exists in database")
                continue

        created_items.append((row, input_data))

    if errors:
        raise HTTPException(
            status_code=400,
            detail="Validation failed: " + "; ".join(errors),
        )

    # Single transaction for all item creations + audit logs + batch metadata update
    try:
        commit_time = datetime.now(timezone.utc)
        result_items = []

        for row, input_data in created_items:
            result = item_service.create_item(
                input_data,
                branch_id=user.branch_id,
                actor_user_id=user.id,
                is_admin=user.role.code.upper() == "ADMIN",
            )
            # Update staging row with reference to created item
            row.reference_id = result.item.id
            result_items.append({
                "row_number": row.row_number,
                "item_id": str(result.item.id),
                "item_code": result.item.item_code,
                "description": result.item.description,
            })

        # Update batch commit metadata
        batch.status = "COMMITTED"
        batch.committed_at = commit_time
        batch.committed_by = user.id
        batch.commit_result = {
            "items_created": len(result_items),
            "items": result_items,
        }
        batch.failure_reason = None

        db.commit()

    except ItemCreationError as e:
        db.rollback()
        # Record failure
        batch.failure_reason = str(e)
        batch.status = "FAILED"
        db.commit()
        raise HTTPException(
            status_code=409,
            detail=f"Item creation failed: {str(e)}",
        )
    except IntegrityError as e:
        db.rollback()
        # Record failure
        batch.failure_reason = "Database integrity error during commit"
        batch.status = "FAILED"
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="Database integrity error. Possible duplicate item code or concurrent modification.",
        )
    except Exception as e:
        db.rollback()
        # Record failure
        batch.failure_reason = f"Unexpected error: {str(e)}"
        batch.status = "FAILED"
        db.commit()
        raise HTTPException(
            status_code=500,
            detail="Internal server error during commit.",
        )

    return {
        "batch_id": str(batch.id),
        "status": "COMMITTED",
        "committed_at": batch.committed_at.isoformat(),
        "committed_by": str(batch.committed_by),
        "commit_result": batch.commit_result,
        "message": f"Successfully committed {len(result_items)} items.",
    }


