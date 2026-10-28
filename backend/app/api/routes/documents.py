from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.api.deps import db_session, require_permission
from app.models.master import User
from app.models.sales import Sale, SaleLine, Repair, RepairPayment, CreditSettlement
from app.models.inventory import SerializedUnit
from app.models.master import Item
from app.models.warranty import ProductWarranty
from app.models.security import DocumentEvent
from app.schemas.api import DocumentSearchOut
from datetime import datetime, timezone

router=APIRouter(prefix='/documents',tags=['documents'])

@router.get('/search',response_model=list[DocumentSearchOut])
def search(q:str,user:User=Depends(require_permission('DOCUMENT_REPRINT')),db:Session=Depends(db_session)):
    q=q.strip()
    if not q: return []
    admin=user.role.code.upper()=='ADMIN'   # Requirements 02: a cashier reprints only their OWN completed sales
    own=() if admin else (Sale.cashier_id==user.id,)
    sales=db.scalars(select(Sale).where(Sale.branch_id==user.branch_id,*own,or_(Sale.invoice_no.ilike(f'%{q}%'),Sale.manual_invoice_ref.ilike(f'%{q}%'))).order_by(Sale.sale_datetime.desc()).limit(20)).all()
    repairs=db.scalars(select(Repair).where(Repair.branch_id==user.branch_id,Repair.repair_no.ilike(f'%{q}%')).order_by(Repair.date_in.desc()).limit(20)).all()
    repair_payments=db.scalars(select(RepairPayment).join(Repair,Repair.id==RepairPayment.repair_id).where(Repair.branch_id==user.branch_id,or_(RepairPayment.proof_no.ilike(f'%{q}%'),RepairPayment.reference.ilike(f'%{q}%'))).order_by(RepairPayment.payment_datetime.desc()).limit(20)).all()
    settlements=[] if not admin else db.scalars(select(CreditSettlement).where(CreditSettlement.branch_id==user.branch_id,or_(CreditSettlement.proof_no.ilike(f'%{q}%'),CreditSettlement.reference.ilike(f'%{q}%'))).order_by(CreditSettlement.settlement_datetime.desc()).limit(20)).all()
    serial_sales=db.scalars(select(Sale).join(SaleLine,SaleLine.sale_id==Sale.id).join(ProductWarranty,ProductWarranty.sale_line_id==SaleLine.id).join(SerializedUnit,SerializedUnit.id==ProductWarranty.serialized_unit_id).where(Sale.branch_id==user.branch_id,*own,SerializedUnit.serial_number.ilike(f'%{q}%')).order_by(Sale.sale_datetime.desc()).limit(20)).all()
    seen={str(x.id) for x in sales}
    sales += [x for x in serial_sales if str(x.id) not in seen]
    return [DocumentSearchOut(document_type='SALE',document_id=x.id,document_no=x.invoice_no,document_datetime=x.sale_datetime,status=x.status) for x in sales]+[DocumentSearchOut(document_type='REPAIR',document_id=x.id,document_no=x.repair_no,document_datetime=x.date_in,status=x.status) for x in repairs]+[DocumentSearchOut(document_type='REPAIR_PAYMENT',document_id=x.id,document_no=x.proof_no or str(x.id),document_datetime=x.payment_datetime,status=x.payment_type) for x in repair_payments]+[DocumentSearchOut(document_type='SETTLEMENT',document_id=x.id,document_no=x.proof_no or str(x.id),document_datetime=x.settlement_datetime,status='COMPLETED') for x in settlements]

@router.post('/{document_type}/{document_id}/reprint')
def reprint(document_type:str,document_id:str,user:User=Depends(require_permission('DOCUMENT_REPRINT')),db:Session=Depends(db_session)):
    dtype=document_type.upper()
    if dtype=='SALE':
        row=db.scalar(select(Sale).where(Sale.id==document_id,Sale.branch_id==user.branch_id))
        if not row: raise HTTPException(404,'Sale document not found')
        if user.role.code.upper()!='ADMIN' and row.cashier_id!=user.id: raise HTTPException(403,'Cashiers can reprint only their own sales')
    elif dtype=='REPAIR':
        row=db.scalar(select(Repair).where(Repair.id==document_id,Repair.branch_id==user.branch_id))
        if not row: raise HTTPException(404,'Repair document not found')
    elif dtype=='REPAIR_PAYMENT':
        row=db.scalar(select(RepairPayment).join(Repair,Repair.id==RepairPayment.repair_id).where(RepairPayment.id==document_id,Repair.branch_id==user.branch_id))
        if not row: raise HTTPException(404,'Repair payment proof not found')
    elif dtype=='SETTLEMENT':
        if user.role.code.upper()!='ADMIN': raise HTTPException(403,'Settlement proofs are Admin-only')
        row=db.scalar(select(CreditSettlement).where(CreditSettlement.id==document_id,CreditSettlement.branch_id==user.branch_id))
        if not row: raise HTTPException(404,'Settlement proof not found')
    else: raise HTTPException(400,'Unsupported document type')
    event=DocumentEvent(document_type=dtype,document_id=row.id,event_type='REPRINT',actor_user_id=user.id,occurred_at=datetime.now(timezone.utc),reason='User requested reprint')
    db.add(event); db.commit()
    return {'document_type':dtype,'document_id':str(row.id),'event_type':'REPRINT','reprint_event_id':str(event.id)}
