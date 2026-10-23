from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import db_session, require_permission
from app.models.master import User, Supplier, Item
from app.models.inventory import Purchase, PurchaseLine
from app.schemas.api import PurchaseCostIn, PendingPurchaseLineOut, PurchaseCostCorrectionIn, PurchaseDateCorrectionIn, PurchaseQuantityCorrectionIn, PurchaseReferenceCorrectionIn
from app.schemas.purchases import PurchaseCreateIn, PurchaseHistoryLineOut
from app.services.purchases import PurchaseService
from app.security.reauth import require_admin_reauth

router=APIRouter(prefix="/purchases",tags=["purchases"])


@router.post("")
def create_purchase(payload: PurchaseCreateIn, user: User = Depends(require_permission("PURCHASE_ENTRY")), db: Session = Depends(db_session)):
    try:
        purchase = PurchaseService(db).create_purchase(
            branch_id=user.branch_id, actor_user_id=user.id, purchase_date=payload.purchase_date,
            lines=[x.model_dump() for x in payload.lines], reference_no=payload.reference_no, notes=payload.notes,
            supplier_id=payload.supplier_id if user.role.code.upper() == "ADMIN" else None,
            admin_side=user.role.code.upper() == "ADMIN", idempotency_key=payload.idempotency_key,
        )
        db.commit()
    except ValueError as exc:
        db.rollback(); raise HTTPException(400, str(exc))
    return {"purchase_id": str(purchase.id), "status": purchase.status, "reference_no": purchase.reference_no,
            "purchase_date": purchase.purchase_date, "line_count": len(payload.lines)}

@router.post("/complete-cost")
def complete_cost(payload:PurchaseCostIn,user:User=Depends(require_permission("PURCHASE_COST")),db:Session=Depends(db_session)):
    purchase=db.scalar(select(Purchase).where(Purchase.id==payload.purchase_id,Purchase.branch_id==user.branch_id).with_for_update())
    line=db.scalar(select(PurchaseLine).where(PurchaseLine.id==payload.purchase_line_id,PurchaseLine.purchase_id==payload.purchase_id).with_for_update())
    if not purchase or not line:
        raise HTTPException(404,"Purchase or purchase line not found")
    if payload.version is None or payload.purchase_version is None: raise HTTPException(409,'Purchase versions are required; reload the record')
    if payload.version is not None and line.version != payload.version: raise HTTPException(409,'Purchase line changed; reload before editing')
    if payload.purchase_version is not None and purchase.version != payload.purchase_version: raise HTTPException(409,'Purchase changed; reload before editing')
    try:
        PurchaseService(db).complete_line_cost(purchase=purchase,line=line,unit_cost=payload.unit_cost,actor_user_id=user.id)
        line.version += 1; purchase.version += 1
        db.commit()
    except ValueError as exc:
        db.rollback(); raise HTTPException(400,str(exc))
    return {"purchase_id":str(purchase.id),"purchase_line_id":str(line.id),"unit_cost":line.unit_cost,"status":purchase.status}


@router.get('/pending-costs', response_model=list[PendingPurchaseLineOut], dependencies=[Depends(require_permission('PURCHASE_COST'))])
def pending_costs(user: User=Depends(require_permission('PURCHASE_COST')), db: Session=Depends(db_session)):
    rows=db.execute(select(Purchase, PurchaseLine).join(PurchaseLine, PurchaseLine.purchase_id==Purchase.id).where(Purchase.branch_id==user.branch_id, PurchaseLine.unit_cost.is_(None)).order_by(Purchase.purchase_date, PurchaseLine.created_at)).all()
    return [PendingPurchaseLineOut(version=l.version,purchase_version=p.version,purchase_id=p.id,purchase_line_id=l.id,purchase_date=p.purchase_date,reference_no=p.reference_no,item_id=l.item_id,quantity=l.quantity,unit_cost=l.unit_cost) for p,l in rows]



@router.get('/history', response_model=list[PurchaseHistoryLineOut], dependencies=[Depends(require_permission('PURCHASE_COST'))])
def purchase_history(user: User = Depends(require_permission('PURCHASE_COST')), db: Session = Depends(db_session)):
    rows = db.execute(
        select(Purchase, PurchaseLine, Supplier, Item)
        .join(PurchaseLine, PurchaseLine.purchase_id == Purchase.id)
        .outerjoin(Supplier, Supplier.id == Purchase.supplier_id)
        .join(Item, Item.id == PurchaseLine.item_id)
        .where(Purchase.branch_id == user.branch_id)
        .order_by(Purchase.purchase_date.desc(), Purchase.created_at.desc(), PurchaseLine.created_at)
        .limit(500)
    ).all()
    return [
        PurchaseHistoryLineOut(
            version=l.version, purchase_version=p.version, purchase_id=p.id, purchase_line_id=l.id, purchase_date=p.purchase_date,
            line_date=l.line_date, reference_no=p.reference_no, supplier_id=p.supplier_id,
            supplier_name=s.name if s else None, item_id=l.item_id, item_code=i.item_code, item_description=i.description,
            quantity=l.quantity, unit_cost=l.unit_cost, status=p.status
        ) for p,l,s,i in rows
    ]


@router.put('/{purchase_id}/supplier')
def set_purchase_supplier(purchase_id: str, supplier_id: str | None = None, version: int | None = None, admin_password: str|None=None,
                          user: User=Depends(require_permission('PURCHASE_COST')), db: Session=Depends(db_session)):
    require_admin_reauth(user=user,password=admin_password,db=db,action='purchase supplier assignment')
    purchase=db.scalar(select(Purchase).where(Purchase.id==purchase_id,Purchase.branch_id==user.branch_id).with_for_update())
    if not purchase:
        raise HTTPException(404,'Purchase not found')
    if version is None: raise HTTPException(409,'Purchase version is required; reload the record')
    if version is not None and purchase.version != version: raise HTTPException(409,'Purchase changed; reload before editing')
    supplier = None
    if supplier_id:
        supplier=db.scalar(select(Supplier).where(Supplier.id==supplier_id,Supplier.is_active.is_(True)))
        if not supplier:
            raise HTTPException(404,'Supplier not found')
    old=str(purchase.supplier_id) if purchase.supplier_id else None
    purchase.supplier_id=supplier.id if supplier else None
    from app.models.security import AuditLog
    from datetime import datetime, timezone
    db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='PURCHASE_SUPPLIER_CORRECTED',
                    entity_type='PURCHASE',entity_id=purchase.id,timestamp=datetime.now(timezone.utc),
                    before_json={'supplier_id':old},after_json={'supplier_id':str(purchase.supplier_id) if purchase.supplier_id else None},
                    source_transaction_id=purchase.id,reason='Admin supplier assignment'))
    db.commit()
    return {'purchase_id':str(purchase.id),'supplier_id':str(purchase.supplier_id) if purchase.supplier_id else None,
            'supplier_name':supplier.name if supplier else None,'status':'CORRECTED'}

@router.post('/correct-cost')
def correct_cost(payload: PurchaseCostCorrectionIn, admin_password: str|None=None, user: User=Depends(require_permission('PURCHASE_COST')), db: Session=Depends(db_session)):
    require_admin_reauth(user=user,password=admin_password,db=db,action='purchase cost correction')
    line=db.scalar(select(PurchaseLine).join(Purchase).where(PurchaseLine.id==payload.purchase_line_id, Purchase.branch_id==user.branch_id).with_for_update())
    if not line: raise HTTPException(404,'Purchase line not found')
    if payload.version is None: raise HTTPException(409,'Purchase line version is required; reload the record')
    if line.version != payload.version: raise HTTPException(409,'Purchase line changed; reload before editing')
    try:
        from app.services.purchase_correction import PurchaseCorrectionService, PurchaseCorrectionError
        old, lot, recalculation=PurchaseCorrectionService(db).change_cost(purchase_line=line,new_cost=payload.unit_cost,reason=payload.reason,actor_user_id=user.id)
        line.version += 1
        db.commit()
    except (ValueError, PurchaseCorrectionError) as exc:
        db.rollback(); raise HTTPException(400,str(exc))
    return {'purchase_line_id':str(line.id),'old_cost':old,'new_cost':lot.unit_cost,'status':'RECALCULATED' if recalculation['allocation_count'] else 'CORRECTED','recalculation':{k:str(v) for k,v in recalculation.items()}}


@router.post('/correct-date')
def correct_date(payload: PurchaseDateCorrectionIn, admin_password: str|None=None, user: User=Depends(require_permission('PURCHASE_COST')), db: Session=Depends(db_session)):
    require_admin_reauth(user=user,password=admin_password,db=db,action='purchase date correction')
    line=db.scalar(select(PurchaseLine).join(Purchase).where(PurchaseLine.id==payload.purchase_line_id, Purchase.branch_id==user.branch_id).with_for_update())
    if not line: raise HTTPException(404,'Purchase line not found')
    if payload.version is None: raise HTTPException(409,'Purchase line version is required; reload the record')
    if line.version != payload.version: raise HTTPException(409,'Purchase line changed; reload before editing')
    try:
        from app.services.purchase_correction import PurchaseCorrectionService, PurchaseCorrectionError
        old, lot=PurchaseCorrectionService(db).change_date(purchase_line=line,new_date=payload.line_date,reason=payload.reason,actor_user_id=user.id)
        line.version += 1
        db.commit()
    except (ValueError, PurchaseCorrectionError) as exc:
        db.rollback(); raise HTTPException(400,str(exc))
    return {'purchase_line_id':str(line.id),'old_date':old,'new_date':lot.lot_date,'status':'CORRECTED'}


@router.post('/correct-quantity')
def correct_quantity(payload: PurchaseQuantityCorrectionIn, admin_password: str|None=None, user: User=Depends(require_permission('PURCHASE_COST')), db: Session=Depends(db_session)):
    require_admin_reauth(user=user,password=admin_password,db=db,action='purchase quantity correction')
    line=db.scalar(select(PurchaseLine).join(Purchase).where(PurchaseLine.id==payload.purchase_line_id, Purchase.branch_id==user.branch_id).with_for_update())
    if not line: raise HTTPException(404,'Purchase line not found')
    if payload.version is None: raise HTTPException(409,'Purchase line version is required; reload the record')
    if line.version != payload.version: raise HTTPException(409,'Purchase line changed; reload before editing')
    try:
        from app.services.purchase_correction import PurchaseCorrectionService, PurchaseCorrectionError
        old,new,lot=PurchaseCorrectionService(db).change_quantity(purchase_line=line,new_quantity=payload.quantity,reason=payload.reason,actor_user_id=user.id)
        line.version += 1
        db.commit()
    except (ValueError, PurchaseCorrectionError) as exc:
        db.rollback(); raise HTTPException(400,str(exc))
    return {'purchase_line_id':str(line.id),'old_quantity':old,'new_quantity':new,'remaining_quantity':lot.remaining_quantity,'status':'CORRECTED'}


@router.post('/correct-reference')
def correct_reference(payload: PurchaseReferenceCorrectionIn, admin_password: str|None=None, user: User=Depends(require_permission('PURCHASE_COST')), db: Session=Depends(db_session)):
    require_admin_reauth(user=user,password=admin_password,db=db,action='purchase reference correction')
    purchase=db.scalar(select(Purchase).where(Purchase.id==payload.purchase_id,Purchase.branch_id==user.branch_id).with_for_update())
    if not purchase: raise HTTPException(404,'Purchase not found')
    if payload.version is None: raise HTTPException(409,'Purchase version is required; reload the record')
    if purchase.version != payload.version: raise HTTPException(409,'Purchase changed; reload before editing')
    old=purchase.reference_no; purchase.reference_no=payload.reference_no; purchase.version += 1
    from app.models.security import AuditLog
    from datetime import datetime, timezone
    db.add(AuditLog(branch_id=user.branch_id,actor_user_id=user.id,action_type='PURCHASE_REFERENCE_CORRECTED',entity_type='PURCHASE',entity_id=purchase.id,timestamp=datetime.now(timezone.utc),reason=payload.reason,before_json={'reference_no':old},after_json={'reference_no':purchase.reference_no},source_transaction_id=purchase.id))
    db.commit(); return {'purchase_id':str(purchase.id),'old_reference_no':old,'reference_no':purchase.reference_no,'status':'CORRECTED'}
