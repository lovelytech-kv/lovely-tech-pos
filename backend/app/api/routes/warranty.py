from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import date
from app.api.deps import db_session, require_permission
from app.models.master import User
from app.schemas.api import WarrantyClaimIn, WarrantyDecisionIn, WarrantyReplacementIn, ManualWarrantyRegistrationIn, WarrantySupplierOutcomeIn
from app.services.warranty import WarrantyService, WarrantyClaimRequest, WarrantyValidationError
from app.models.warranty import ProductWarranty, ManualWarrantyDocument, WarrantyDocumentEvent
from app.services.warranty_calculator import calculate_expiry, warranty_status, WarrantyCalculationError
from app.services.numbering import NumberingService

router = APIRouter(prefix="/warranty", tags=["warranty"])

def run(db, fn):
    try:
        result=fn(); db.commit(); return result
    except WarrantyValidationError as exc:
        db.rollback(); raise HTTPException(400,str(exc))


@router.get('/calculator')
def warranty_calculator(start_date: date, warranty_type: str, duration_value: int | None = None, custom_rule: str | None = None, user: User=Depends(require_permission('WARRANTY_CREATE'))):
    try:
        expiry=calculate_expiry(start_date, warranty_type, duration_value, custom_rule)
        return {'start_date':start_date,'expiry_date':expiry,'status':warranty_status(start_date, expiry, date.today()),'warranty_type':warranty_type}
    except WarrantyCalculationError as exc:
        raise HTTPException(400,str(exc))

@router.get('/lookup')
def warranty_lookup(warranty_no: str, user: User=Depends(require_permission('WARRANTY_CREATE')), db: Session=Depends(db_session)):
    row=db.scalar(select(ProductWarranty).where(ProductWarranty.branch_id==user.branch_id, ProductWarranty.warranty_no==warranty_no).with_for_update())
    if row is None: raise HTTPException(404,'Warranty not found')
    status=warranty_status(row.start_date,row.expiry_date,date.today())
    if row.status != status and status in {'EXPIRED','ACTIVE'}:
        row.status=status
        db.commit()
    return {'warranty_id':str(row.id),'warranty_no':row.warranty_no,'start_date':row.start_date,'expiry_date':row.expiry_date,'warranty_type':row.warranty_type,'duration_value':row.duration_value,'custom_rule':row.custom_rule,'status':status}


@router.post('/manual-registration')
def manual_registration(payload: ManualWarrantyRegistrationIn, user: User=Depends(require_permission('WARRANTY_DECIDE')), db: Session=Depends(db_session)):
    try:
        if payload.expiry_date is not None and payload.expiry_date < payload.start_date:
            raise WarrantyValidationError('Expiry date cannot be before start date')
        doc=ManualWarrantyDocument(branch_id=user.branch_id,reference_no=payload.reference_no.strip(),customer_name=payload.customer_name,item_description=payload.item_description,notes=payload.notes)
        db.add(doc); db.flush()
        warranty=ProductWarranty(branch_id=user.branch_id,warranty_no=NumberingService.next_number(db,'MWR',str(user.branch_id)),start_date=payload.start_date,expiry_date=payload.expiry_date,warranty_type=payload.warranty_type,source='MANUAL_EXCEPTION',status=warranty_status(payload.start_date,payload.expiry_date,date.today()))
        db.add(warranty); db.flush()
        db.add(WarrantyDocumentEvent(manual_document_id=doc.id,warranty_id=warranty.id,event_type='ORIGINAL',actor_user_id=user.id))
        db.commit()
        return {'manual_document_id':str(doc.id),'warranty_id':str(warranty.id),'warranty_no':warranty.warranty_no,'status':warranty.status}
    except (WarrantyValidationError, ValueError) as exc:
        db.rollback(); raise HTTPException(400,str(exc))

@router.post('/claims/{claim_id}/supplier-outcome')
def supplier_outcome(claim_id:str,payload:WarrantySupplierOutcomeIn,user:User=Depends(require_permission('WARRANTY_DECIDE')),db:Session=Depends(db_session)):
    if payload.version is None: raise HTTPException(409,'Warranty claim version is required; reload the claim')
    c=run(db, lambda: WarrantyService(db).record_supplier_outcome(claim_id,user.branch_id,user.id,version=payload.version,outcome=payload.outcome,quantity=payload.quantity,notes=payload.notes))
    return {'claim_id':str(c.id),'status':c.admin_decision,'replacement_outcome':c.replacement_outcome}

@router.post("/claims")
def create_claim(payload: WarrantyClaimIn, user: User=Depends(require_permission("WARRANTY_CREATE")), db: Session=Depends(db_session)):
    c=run(db, lambda: WarrantyService(db).create_claim(WarrantyClaimRequest(branch_id=user.branch_id, created_by=user.id, **payload.model_dump())))
    return {"claim_id":str(c.id),"claim_no":c.claim_no,"status":c.admin_decision}

@router.post("/claims/{claim_id}/supplier")
def supplier_decision(claim_id:str,payload:WarrantyDecisionIn,user:User=Depends(require_permission("WARRANTY_DECIDE")),db:Session=Depends(db_session)):
    if payload.version is None: raise HTTPException(409,'Warranty claim version is required; reload the claim')
    c=run(db, lambda: WarrantyService(db).decide_supplier_claim(claim_id,user.branch_id,user.id,version=payload.version,supplier_process=payload.supplier_process,notes=payload.notes))
    return {"claim_id":str(c.id),"status":c.admin_decision}

@router.post("/claims/{claim_id}/damage")
def damage_decision(claim_id:str,payload:WarrantyDecisionIn,user:User=Depends(require_permission("WARRANTY_DECIDE")),db:Session=Depends(db_session)):
    if payload.version is None: raise HTTPException(409,'Warranty claim version is required; reload the claim')
    c=run(db, lambda: WarrantyService(db).decide_damage(claim_id,user.branch_id,user.id,version=payload.version,reason=payload.notes or "Warranty damage/loss"))
    return {"claim_id":str(c.id),"status":c.admin_decision}

@router.post("/claims/{claim_id}/replacement")
def replacement(claim_id:str,payload:WarrantyReplacementIn,user:User=Depends(require_permission("WARRANTY_DECIDE")),db:Session=Depends(db_session)):
    if payload.version is None: raise HTTPException(409,'Warranty claim version is required; reload the claim')
    c=run(db, lambda: WarrantyService(db).record_supplier_replacement(claim_id,user.branch_id,user.id,version=payload.version,quantity=payload.quantity))
    return {"claim_id":str(c.id),"status":c.replacement_outcome}


@router.get('/claims')
def list_claims(user: User=Depends(require_permission('WARRANTY_CREATE')), db: Session=Depends(db_session)):
    from app.models.warranty import WarrantyClaim
    rows=db.scalars(select(WarrantyClaim).where(WarrantyClaim.branch_id==user.branch_id).order_by(WarrantyClaim.created_at.desc()).limit(100)).all()
    return [{'claim_id':str(c.id),'claim_no':c.claim_no,'version':c.version,'item_id':str(c.item_id),'quantity':c.holding_quantity,'admin_decision':c.admin_decision,'replacement_outcome':c.replacement_outcome,'notes':c.notes} for c in rows]


@router.get('/serial-lookup')
def warranty_serial_lookup(serial_number: str, user: User = Depends(require_permission('WARRANTY_CREATE')), db: Session = Depends(db_session)):
    from app.models.inventory import SerializedUnit
    from app.models.master import Item
    row = db.execute(select(ProductWarranty, SerializedUnit, Item).join(SerializedUnit, SerializedUnit.id == ProductWarranty.serialized_unit_id).join(Item, Item.id == SerializedUnit.item_id).where(ProductWarranty.branch_id == user.branch_id, SerializedUnit.serial_number == serial_number.strip()).order_by(ProductWarranty.created_at.desc())).first()
    if row is None:
        raise HTTPException(404, 'Warranty for serial/IMEI not found')
    warranty, unit, item = row
    status = warranty_status(warranty.start_date, warranty.expiry_date, date.today())
    if warranty.status != status and status in {'EXPIRED','ACTIVE'}:
        warranty.status = status; db.commit()
    return {'warranty_id': str(warranty.id), 'warranty_no': warranty.warranty_no, 'serial_number': unit.serial_number, 'item_code': item.item_code, 'description': item.description, 'start_date': warranty.start_date, 'expiry_date': warranty.expiry_date, 'status': status}
