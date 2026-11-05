from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.api.deps import db_session, require_permission
from app.models.master import User
from app.models.sales import Sale, SaleLine, Repair, RepairPayment, CreditSettlement, Customer
from app.models.inventory import SerializedUnit
from app.models.master import Item
from app.models.warranty import ProductWarranty
from app.models.security import DocumentEvent
from app.schemas.api import DocumentSearchOut
from datetime import date, datetime, time, timedelta, timezone

router=APIRouter(prefix='/documents',tags=['documents'])

@router.get('/search',response_model=list[DocumentSearchOut])
@router.get('')
def list_documents(
    date_from: date | None = None,
    date_to: date | None = None,
    document_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(require_permission('DOCUMENT_REPRINT')),
    db: Session = Depends(db_session),
):
    """List all documents across sales, repairs, repair payments and settlements.

    Permission: same as /documents/search — Admin sees all, Cashier sees only their own sales.
    Settlement proofs are Admin-only (as in /search).

    Default date range is today. Pagination via limit/offset with has_more flag.
    """
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    is_admin = user.role.code.upper() == 'ADMIN'

    if date_from is None and date_to is None:
        today_local = datetime.now(timezone.utc).date()
        date_from = today_local
        date_to = today_local

    dt_from = datetime.combine(date_from, time.min, tzinfo=timezone.utc) if date_from else None
    dt_to_excl = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc) if date_to else None

    like = f'%{q.strip()}%' if q and q.strip() else None
    wanted = document_type.strip().upper() if document_type else None
    want_status = status.strip().upper() if status else None

    def rng(col):
        conds = []
        if dt_from is not None:
            conds.append(col >= dt_from)
        if dt_to_excl is not None:
            conds.append(col < dt_to_excl)
        return conds

    fetch_cap = offset + limit
    results = []

    # ---- SALES ----
    if not wanted or wanted == 'SALE':
        stmt = select(Sale).where(Sale.branch_id == user.branch_id)
        if not is_admin:
            stmt = stmt.where(Sale.cashier_id == user.id)
        for c in rng(Sale.sale_datetime):
            stmt = stmt.where(c)
        if like:
            stmt = stmt.where(
                or_(
                    Sale.invoice_no.ilike(like),
                    Sale.manual_invoice_ref.ilike(like),
                    Sale.customer_id.in_(
                        select(Customer.id).where(
                            or_(Customer.name.ilike(like), Customer.contact_no.ilike(like))
                        )
                    ),
                    Sale.id.in_(
                        select(SaleLine.sale_id)
                        .join(Item, Item.id == SaleLine.item_id)
                        .where(or_(Item.description.ilike(like), Item.item_code.ilike(like)))
                    ),
                )
            )
        if want_status:
            stmt = stmt.where(Sale.status == want_status)
        for s in db.scalars(stmt.order_by(Sale.sale_datetime.desc()).limit(fetch_cap)).all():
            results.append({
                'document_type': 'SALE',
                'document_id': str(s.id),
                'document_no': s.invoice_no,
                'document_datetime': s.sale_datetime,
                'status': s.status,
            })

    # ---- REPAIRS ----
    if not wanted or wanted == 'REPAIR':
        stmt = select(Repair).where(Repair.branch_id == user.branch_id)
        for c in rng(Repair.date_in):
            stmt = stmt.where(c)
        if like:
            stmt = stmt.where(
                or_(
                    Repair.repair_no.ilike(like),
                    Repair.customer_name.ilike(like),
                    Repair.contact_no.ilike(like),
                )
            )
        if want_status:
            stmt = stmt.where(Repair.status == want_status)
        for r in db.scalars(stmt.order_by(Repair.date_in.desc()).limit(fetch_cap)).all():
            results.append({
                'document_type': 'REPAIR',
                'document_id': str(r.id),
                'document_no': r.repair_no,
                'document_datetime': r.date_in,
                'status': r.status,
            })

    # ---- REPAIR PAYMENTS ----
    if not wanted or wanted == 'REPAIR_PAYMENT':
        stmt = (
            select(RepairPayment, Repair)
            .join(Repair, Repair.id == RepairPayment.repair_id)
            .where(Repair.branch_id == user.branch_id)
        )
        for c in rng(RepairPayment.payment_datetime):
            stmt = stmt.where(c)
        if like:
            stmt = stmt.where(
                or_(
                    RepairPayment.proof_no.ilike(like),
                    RepairPayment.reference.ilike(like),
                    Repair.repair_no.ilike(like),
                )
            )
        if want_status:
            stmt = stmt.where(RepairPayment.payment_type == want_status)
        for p, _repair in db.execute(stmt.order_by(RepairPayment.payment_datetime.desc()).limit(fetch_cap)).all():
            results.append({
                'document_type': 'REPAIR_PAYMENT',
                'document_id': str(p.id),
                'document_no': p.proof_no or str(p.id),
                'document_datetime': p.payment_datetime,
                'status': p.payment_type,
            })

    # ---- SETTLEMENTS (admin only, matching /search behavior) ----
    if (not wanted or wanted == 'SETTLEMENT') and is_admin:
        stmt = select(CreditSettlement).where(CreditSettlement.branch_id == user.branch_id)
        for c in rng(CreditSettlement.settlement_datetime):
            stmt = stmt.where(c)
        if like:
            stmt = stmt.where(
                or_(
                    CreditSettlement.proof_no.ilike(like),
                    CreditSettlement.reference.ilike(like),
                )
            )
        for s in db.scalars(stmt.order_by(CreditSettlement.settlement_datetime.desc()).limit(fetch_cap)).all():
            results.append({
                'document_type': 'SETTLEMENT',
                'document_id': str(s.id),
                'document_no': s.proof_no or str(s.id),
                'document_datetime': s.settlement_datetime,
                'status': 'COMPLETED',
            })

    results.sort(key=lambda x: x['document_datetime'], reverse=True)
    total = len(results)
    paged = results[offset:offset + limit]

    return {
        'items': paged,
        'total': total,
        'has_more': offset + limit < total,
    }
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
    # Lost-bill recovery (Requirements 10): also find sales by customer, item and date.
    like=f'%{q}%'
    conds=[Customer.name.ilike(like),Customer.contact_no.ilike(like),Item.description.ilike(like),Item.item_code.ilike(like)]
    try: conds.append(func.date(Sale.sale_datetime)==date.fromisoformat(q))
    except ValueError: pass
    other_sales=db.scalars(select(Sale).outerjoin(Customer,Customer.id==Sale.customer_id).join(SaleLine,SaleLine.sale_id==Sale.id).join(Item,Item.id==SaleLine.item_id).where(Sale.branch_id==user.branch_id,*own,or_(*conds)).distinct().order_by(Sale.sale_datetime.desc()).limit(20)).all()
    seen={str(x.id) for x in sales}
    sales += [x for x in serial_sales+other_sales if str(x.id) not in seen and not seen.add(str(x.id))]
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
