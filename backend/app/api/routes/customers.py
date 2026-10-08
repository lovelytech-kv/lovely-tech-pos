from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from app.api.deps import db_session, require_permission
from app.models.master import User
from app.models.sales import Customer, Sale, CreditSettlement, Repair, SaleLine
from app.schemas.api import CustomerIn, CustomerUpdateIn
from app.models.security import AuditLog
from app.models.warranty import WarrantyClaim, ProductWarranty

router = APIRouter(prefix="/customers", tags=["customers"])

@router.get("")
def list_customers(q: str = "", user: User = Depends(require_permission("SALE_CREATE")), db: Session = Depends(db_session)):
    term = q.strip()
    stmt = select(Customer).where(Customer.is_active.is_(True))
    if term:
        like = f"%{term}%"
        stmt = stmt.where(or_(Customer.name.ilike(like), Customer.contact_no.ilike(like)))
    rows = db.scalars(stmt.order_by(Customer.name.nullslast(), Customer.created_at.desc()).limit(50)).all()
    return [{"customer_id": str(x.id), "name": x.name, "contact_no": x.contact_no, "notes": x.notes, "version": x.version} for x in rows]

@router.post("")
def create_customer(payload: CustomerIn, user: User = Depends(require_permission("SALE_CREATE")), db: Session = Depends(db_session)):
    row = Customer(name=payload.name, contact_no=payload.contact_no, notes=payload.notes)
    db.add(row); db.flush()
    db.add(AuditLog(branch_id=user.branch_id, actor_user_id=user.id, action_type="CUSTOMER_CREATED", entity_type="CUSTOMER", entity_id=row.id, timestamp=datetime.now(timezone.utc), after_json={"name":row.name,"contact_no":row.contact_no}, source_transaction_id=row.id))
    db.commit()
    return {"customer_id":str(row.id),"name":row.name,"contact_no":row.contact_no,"version":row.version}

@router.put("/{customer_id}")
def update_customer(customer_id: str, payload: CustomerUpdateIn, user: User = Depends(require_permission("SALE_CREATE")), db: Session = Depends(db_session)):
    row = db.scalar(select(Customer).where(Customer.id==customer_id, Customer.is_active.is_(True)).with_for_update())
    if not row: raise HTTPException(404,"Customer not found")
    if row.version != payload.version: raise HTTPException(409,"Customer changed; reload before editing")
    before={"name":row.name,"contact_no":row.contact_no,"notes":row.notes}
    row.name=payload.name; row.contact_no=payload.contact_no; row.notes=payload.notes; row.version += 1
    db.add(AuditLog(branch_id=user.branch_id, actor_user_id=user.id, action_type="CUSTOMER_EDITED", entity_type="CUSTOMER", entity_id=row.id, timestamp=datetime.now(timezone.utc), before_json=before, after_json={"name":row.name,"contact_no":row.contact_no,"notes":row.notes}, source_transaction_id=row.id))
    db.commit(); return {"customer_id":str(row.id),"name":row.name,"contact_no":row.contact_no,"notes":row.notes,"version":row.version}

@router.get("/{customer_id}/history")
def customer_history(customer_id:str, user:User=Depends(require_permission("REPORT_VIEW")), db:Session=Depends(db_session)):
    customer=db.get(Customer,customer_id)
    if not customer: raise HTTPException(404,"Customer not found")
    sales=db.scalars(select(Sale).where(Sale.branch_id==user.branch_id,Sale.customer_id==customer.id,Sale.status=="COMPLETED").order_by(Sale.sale_datetime.desc()).limit(100)).all()
    settlements=db.scalars(select(CreditSettlement).where(CreditSettlement.branch_id==user.branch_id,CreditSettlement.customer_id==customer.id).order_by(CreditSettlement.settlement_datetime.desc()).limit(100)).all()
    repairs=db.scalars(select(Repair).where(Repair.branch_id==user.branch_id,Repair.customer_id==customer.id).order_by(Repair.date_in.desc()).limit(100)).all()
    claims=db.execute(
        select(WarrantyClaim, ProductWarranty, Sale, SaleLine)
        .join(ProductWarranty, ProductWarranty.id==WarrantyClaim.product_warranty_id)
        .join(SaleLine, SaleLine.id==ProductWarranty.sale_line_id)
        .join(Sale, Sale.id==SaleLine.sale_id)
        .where(WarrantyClaim.branch_id==user.branch_id, Sale.customer_id==customer.id)
        .order_by(WarrantyClaim.created_at.desc()).limit(100)
    ).all()
    return {"customer":{"customer_id":str(customer.id),"name":customer.name,"contact_no":customer.contact_no},
            "sales":[{"sale_id":str(x.id),"invoice_no":x.invoice_no,"date":x.sale_datetime,"total":x.grand_total} for x in sales],
            "settlements":[{"settlement_id":str(x.id),"date":x.settlement_datetime,"amount":x.amount,"method":x.payment_method,"remaining":x.remaining_outstanding} for x in settlements],
            "repairs":[{"repair_id":str(x.id),"repair_no":x.repair_no,"date":x.date_in,"status":x.status,"total":x.total_amount} for x in repairs],
            "warranty_claims":[{"claim_id":str(c.id),"claim_no":c.claim_no,"date":c.created_at,"decision":c.admin_decision,
                               "outcome":c.replacement_outcome,"item_id":str(c.item_id),"warranty_no":w.warranty_no,
                               "invoice_no":sale.invoice_no} for c,w,sale,line in claims]}
