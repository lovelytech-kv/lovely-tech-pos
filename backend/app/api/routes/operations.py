from datetime import date
from decimal import Decimal
from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.backup.auto import ensure_close_backup
from sqlalchemy.orm import Session
from app.api.deps import db_session, require_permission
from app.models.master import User
from app.schemas.api import *
from app.services.repairs import RepairService, RepairCreateRequest, RepairPaymentInput, RepairPartInput, RepairValidationError
from app.services.day_finance import DayFinanceService, DayFinanceError
from app.services.approvals import ApprovalService, ApprovalError
from app.services.settlements import SettlementService, SettlementError
from app.models.sales import RepairWarranty, Repair
from app.models.security import ApprovalRequest
from app.services.sales import SaleService, SaleRequest, SaleLineInput, PaymentInput
from app.services.warranty_calculator import warranty_status
from app.security.reauth import require_admin_reauth
from app.models.backup import BackupPoint
from datetime import datetime, timezone, time

router=APIRouter(tags=["operations"])

def _close_backup_gate(db: Session, user: User, what: str):
    """Requirements 15: Shift End / Day End complete only after a backup is VERIFIED.

    Returns None when a fresh verified backup exists (the close may proceed). Otherwise an automatic
    backup (with automatic retries) is running in the background and a 202 is returned; the client
    asks again and the close completes as soon as the backup is verified. A job that exhausted its
    retries raises 503 and nothing is closed.
    """
    from app.core.config import settings
    if not settings.require_verified_backup_for_close:
        return None
    st = ensure_close_backup(db, branch_id=user.branch_id, user_id=user.id)
    if st.ready:
        return None
    if st.state == "FAILED":
        raise HTTPException(503, f"BACKUP_FAILED: The automatic backup could not be verified after {st.max_attempts} attempts, "
                                 f"so {what} was NOT completed and nothing was changed. Press the button again to retry, or contact the Admin.")
    return JSONResponse(status_code=202, content=jsonable_encoder(st.as_payload()))

def commit_or_400(db, fn):
    try:
        result=fn(); db.commit(); return result
    except (RepairValidationError,DayFinanceError,ApprovalError,SettlementError,ValueError) as e:
        db.rollback(); raise HTTPException(400,str(e))

@router.post('/repairs', dependencies=[Depends(require_permission('REPAIR_CREATE'))])
def create_repair(payload: RepairCreateIn, user: User=Depends(require_permission('REPAIR_CREATE')), db: Session=Depends(db_session)):
    r=commit_or_400(db, lambda: RepairService(db).create(RepairCreateRequest(branch_id=user.branch_id,actor_user_id=user.id,**payload.model_dump())))
    return {'repair_id':str(r.id),'repair_no':r.repair_no,'status':r.status}

@router.post('/repairs/{repair_id}/status', dependencies=[Depends(require_permission('REPAIR_UPDATE'))])
def repair_status(repair_id:str,payload:RepairStatusIn,user:User=Depends(require_permission('REPAIR_UPDATE')),db:Session=Depends(db_session)):
    if payload.version is None: raise HTTPException(409,'Repair version is required; reload the record')
    auth = user.id if getattr(user.role, 'code', '').upper() == 'ADMIN' else None
    r=commit_or_400(db,lambda:RepairService(db).set_status(repair_id,user.branch_id,user.id,payload.status,version=payload.version,authorized_by=auth)); return {'repair_id':str(r.id),'status':r.status}

@router.get('/repairs/{repair_id}')
def repair_detail(repair_id:str,user:User=Depends(require_permission('REPAIR_CREATE')),db:Session=Depends(db_session)):
    return RepairService(db).detail(repair_id,user.branch_id)

@router.post('/repairs/{repair_id}/payment', dependencies=[Depends(require_permission('REPAIR_PAYMENT'))])
def repair_payment(repair_id:str,payload:RepairPaymentIn,user:User=Depends(require_permission('REPAIR_PAYMENT')),db:Session=Depends(db_session)):
    p=commit_or_400(db,lambda:RepairService(db).add_payment(repair_id,user.branch_id,user.id,RepairPaymentInput(method=payload.method,amount=payload.amount,reference=payload.reference or payload.proof_reference,payment_type=payload.payment_type),idempotency_key=payload.idempotency_key)); return {'payment_id':str(p.id),'amount':p.amount,'method':p.payment_method,'proof_no':p.proof_no}

@router.post('/repairs/{repair_id}/finalize', dependencies=[Depends(require_permission('REPAIR_UPDATE'))])
def repair_finalize(repair_id:str,payload:RepairFinalizeIn,user:User=Depends(require_permission('REPAIR_UPDATE')),db:Session=Depends(db_session)):
    if payload.version is None: raise HTTPException(409,'Repair version is required; reload the record')
    r=commit_or_400(db,lambda:RepairService(db).finalize_amounts(repair_id,user.branch_id,user.id,**payload.model_dump())); return {'repair_id':str(r.id),'total_amount':r.total_amount,'labour_amount':r.labour_amount}

@router.post('/repairs/{repair_id}/deliver', dependencies=[Depends(require_permission('REPAIR_UPDATE'))])
def repair_deliver(repair_id:str, version:int, user:User=Depends(require_permission('REPAIR_UPDATE')), db:Session=Depends(db_session)):
    try:
        admin_override = user.role.code.upper() == "ADMIN"
        r = RepairService(db).deliver(repair_id, user.branch_id, user.id, version=version, admin_override=admin_override)
        db.commit()
        return {'repair_id':str(r.id),'repair_no':r.repair_no,'status':r.status,'hand_over_date':r.hand_over_date,'admin_override':admin_override}
    except RepairValidationError as e:
        db.rollback(); raise HTTPException(400,str(e))

@router.post('/repairs/{repair_id}/cancel', dependencies=[Depends(require_permission('REPAIR_UPDATE'))])
def repair_cancel(repair_id:str,payload:RepairCancelIn,user:User=Depends(require_permission('REPAIR_UPDATE')),db:Session=Depends(db_session)):
    if payload.version is None: raise HTTPException(409,'Repair version is required; reload the record')
    r=commit_or_400(db,lambda:RepairService(db).cancel(repair_id,user.branch_id,user.id,version=payload.version,reason=payload.reason)); return {'repair_id':str(r.id),'status':r.status}

@router.post('/day/start', dependencies=[Depends(require_permission('DAY_MANAGE'))])
def day_start(payload:DayStartIn,user:User=Depends(require_permission('DAY_MANAGE')),db:Session=Depends(db_session)):
    r=commit_or_400(db,lambda:DayFinanceService(db).start_day(branch_id=user.branch_id,user_id=user.id,**payload.model_dump())); return {'day_session_id':str(r.day_session_id),'business_date':r.business_date,'opening_cash':r.opening_cash}

@router.post('/day/opening-correction', dependencies=[Depends(require_permission('DAY_MANAGE'))])
def day_opening_correction(payload:DayOpeningCorrectionIn, admin_password:str|None=None, user:User=Depends(require_permission('DAY_MANAGE')), db:Session=Depends(db_session)):
    if payload.version is None: raise HTTPException(409,'Day version is required; reload the record')
    require_admin_reauth(user=user,password=admin_password,db=db,action='opening cash correction')
    row=commit_or_400(db,lambda:DayFinanceService(db).correct_opening(day_session_id=payload.day_session_id,user_id=user.id,opening_cash=payload.opening_cash,denominations=payload.denominations,reason=payload.reason,version=payload.version))
    return {'day_session_id':str(row.id),'opening_cash':row.opening_cash}

@router.post('/day/continue', dependencies=[Depends(require_permission('DAY_MANAGE'))])
def day_continue(payload:DateRangeIn,user:User=Depends(require_permission('DAY_MANAGE')),db:Session=Depends(db_session)):
    if user.role.code.upper() != 'ADMIN': raise HTTPException(403,'Admin only')
    row=commit_or_400(db,lambda:DayFinanceService(db).continue_day(branch_id=user.branch_id,business_date=payload.start)); return {'day_session_id':str(row.id),'status':row.status}


@router.post('/day/reload', dependencies=[Depends(require_permission('DAY_MANAGE'))])
def day_reload(payload:ReloadIn,user:User=Depends(require_permission('DAY_MANAGE')),db:Session=Depends(db_session)):
    r=commit_or_400(db,lambda:DayFinanceService(db).add_reload(day_session_id=payload.day_session_id,user_id=user.id,provider=payload.provider,amount=payload.amount,note=payload.note)); return {'reload_id':str(r.id),'amount':r.amount,'provider':r.provider}

@router.post('/day/cash-in', dependencies=[Depends(require_permission('DAY_MANAGE'))])
def day_cash_in(payload:CashInIn,user:User=Depends(require_permission('DAY_MANAGE')),db:Session=Depends(db_session)):
    status=DayFinanceService(db)
    row=status._open(user.branch_id,date.today())
    if not row: raise HTTPException(400,'No open business day')
    r=commit_or_400(db,lambda:status.add_other_cash_in(branch_id=user.branch_id,day_session_id=row.id,user_id=user.id,amount=payload.amount,note=payload.note)); return {'cash_in_id':str(r.id),'amount':r.amount}

@router.post('/day/shift-end', dependencies=[Depends(require_permission('DAY_MANAGE'))])
def shift_end(payload: DateRangeIn, user: User=Depends(require_permission('DAY_MANAGE')), db: Session=Depends(db_session)):
    gate = _close_backup_gate(db, user, "Shift End")
    if gate is not None: return gate
    r=commit_or_400(db, lambda: DayFinanceService(db).shift_end(branch_id=user.branch_id, business_date=payload.start, user_id=user.id))
    return {'day_session_id':str(r.id),'status':r.status,'shift_end_at':r.shift_end_at}

@router.post('/day/reopen', dependencies=[Depends(require_permission('DAY_MANAGE'))])
def day_reopen(payload:DateRangeIn, admin_password:str|None=None, user:User=Depends(require_permission('DAY_MANAGE')), db:Session=Depends(db_session)):
    require_admin_reauth(user=user,password=admin_password,db=db,action='Day End reopen')
    row=commit_or_400(db,lambda:DayFinanceService(db).reopen_closed_day(branch_id=user.branch_id,business_date=payload.start,user_id=user.id))
    return {'day_session_id':str(row.id),'status':row.status}

@router.post('/day/{day_session_id}/end', dependencies=[Depends(require_permission('DAY_MANAGE'))])
def day_end(day_session_id:str,payload:DayEndIn,user:User=Depends(require_permission('DAY_MANAGE')),db:Session=Depends(db_session)):
    day = db.get(__import__('app.models.finance', fromlist=['DaySession']).DaySession, day_session_id)
    if not day or day.branch_id != user.branch_id:
        raise HTTPException(404, 'Day session not found')
    gate = _close_backup_gate(db, user, "Day End")
    if gate is not None: return gate
    if payload.version is None: raise HTTPException(409,'Day version is required; reload the record')
    r=commit_or_400(db,lambda:DayFinanceService(db).end_day(day_session_id=day_session_id,user_id=user.id,**payload.model_dump())); return {'day_session_id':str(r.day_session_id),'expected_cash':r.expected_cash,'actual_cash':r.actual_cash,'difference':r.difference}

@router.post('/approvals', dependencies=[Depends(require_permission('APPROVAL_REQUEST'))])
def approval_create(payload:ApprovalCreateIn,user:User=Depends(require_permission('APPROVAL_REQUEST')),db:Session=Depends(db_session)):
    r=commit_or_400(db,lambda:ApprovalService(db).request(branch_id=user.branch_id,requester_user_id=user.id,**payload.model_dump())); return {'approval_id':str(r.id),'status':r.status,'approval_action_id':r.approval_action_id}

@router.post('/approvals/{approval_id}/review', dependencies=[Depends(require_permission('APPROVAL_REVIEW'))])
def approval_review(approval_id:str,payload:ApprovalReviewIn,user:User=Depends(require_permission('APPROVAL_REVIEW')),db:Session=Depends(db_session)):
    try:
        row = db.scalar(select(ApprovalRequest).where(ApprovalRequest.id == approval_id, ApprovalRequest.branch_id == user.branch_id).with_for_update())
        if not row or row.status != 'PENDING':
            raise HTTPException(400, 'Approval request not found or already reviewed')
        if payload.version is None: raise HTTPException(409, 'Approval version is required; reload the record')
        if row.version != payload.version: raise HTTPException(409, 'Approval request changed; reload before reviewing')
        reviewed = ApprovalService(db).review(approval_id, branch_id=user.branch_id, reviewer_user_id=user.id, **{k:v for k,v in payload.model_dump().items() if k != 'version'})
        result = None
        if reviewed.status == 'APPROVED' and reviewed.action_type == 'DISCOUNT_OVERRIDE':
            sale_payload = (reviewed.payload_json or {}).get('sale')
            if not sale_payload:
                raise ValueError('Discount approval payload is missing sale data')
            from uuid import UUID
            from datetime import datetime
            lines = tuple(SaleLineInput(item_id=UUID(x['item_id']), quantity=Decimal(str(x['quantity'])), unit_price=Decimal(str(x['unit_price'])) if x.get('unit_price') is not None else None, discount=Decimal(str(x.get('discount','0'))), serialized_unit_id=UUID(x['serialized_unit_id']) if x.get('serialized_unit_id') else None) for x in sale_payload['lines'])
            payments = tuple(PaymentInput(method=x['method'], amount=Decimal(str(x['amount'])), reference=x.get('reference')) for x in sale_payload.get('payments', []))
            sale_dt = datetime.fromisoformat(sale_payload['sale_datetime']) if sale_payload.get('sale_datetime') else None
            cashier_id = UUID((reviewed.payload_json or {}).get('cashier_id'))
            req = SaleRequest(branch_id=user.branch_id, cashier_id=cashier_id, lines=lines, payments=payments, document_type=sale_payload.get('document_type','SYSTEM_PRINTED'), manual_invoice_ref=sale_payload.get('manual_invoice_ref'), customer_id=UUID(sale_payload['customer_id']) if sale_payload.get('customer_id') else None, sale_datetime=sale_dt, idempotency_key=sale_payload.get('idempotency_key'), credit_sale=bool(sale_payload.get('credit_sale')), cash_received=Decimal(str(sale_payload['cash_received'])) if sale_payload.get('cash_received') is not None else None, admin_discount_approved=True)
            result = SaleService(db).complete(req)
            reviewed.source_transaction_id = result.sale_id
        db.commit()
        return {'approval_id':str(reviewed.id),'status':reviewed.status,'executed_sale_id':str(result.sale_id) if result else None}
    except HTTPException:
        db.rollback(); raise
    except (ApprovalError, ValueError) as e:
        db.rollback(); raise HTTPException(400,str(e))

@router.post('/settlements', dependencies=[Depends(require_permission('CREDIT_SETTLE'))])
def settlement(payload:SettlementIn,user:User=Depends(require_permission('CREDIT_SETTLE')),db:Session=Depends(db_session)):
    r=commit_or_400(db,lambda:SettlementService(db).settle(branch_id=user.branch_id,user_id=user.id,**payload.model_dump())); return {'settlement_id':str(r.id),'proof_no':r.proof_no,'remaining_outstanding':r.remaining_outstanding}

@router.post('/repairs/{repair_id}/part', dependencies=[Depends(require_permission('REPAIR_UPDATE'))])
def repair_part(repair_id:str,payload:RepairPartIn,user:User=Depends(require_permission('REPAIR_UPDATE')),db:Session=Depends(db_session)):
    part=commit_or_400(db,lambda:RepairService(db).add_part(repair_id,user.branch_id,user.id,RepairPartInput(**payload.model_dump())))
    return {'part_id':str(part.id),'quantity':part.quantity,'charge_amount':part.charge_amount,'fifo_cost':part.fifo_cost}



@router.post('/repairs/{repair_id}/part/{part_id}/remove', dependencies=[Depends(require_permission('REPAIR_UPDATE'))])
def repair_part_remove(repair_id:str, part_id:str, payload:RepairPartRemoveIn, user:User=Depends(require_permission('REPAIR_UPDATE')), db:Session=Depends(db_session)):
    part=commit_or_400(db,lambda:RepairService(db).remove_part(repair_id,part_id,user.branch_id,user.id,condition=payload.condition,reason=payload.reason))
    return {'part_id':str(part.id),'status':part.status}

@router.post('/repairs/{repair_id}/part/{part_id}/damage-review', dependencies=[Depends(require_permission('WARRANTY_DECIDE'))])
def repair_part_damage_review(repair_id:str, part_id:str, payload:ApprovalReviewIn, user:User=Depends(require_permission('WARRANTY_DECIDE')), db:Session=Depends(db_session)):
    result=commit_or_400(db,lambda:RepairService(db).review_damaged_part(part_id,user.branch_id,user.id,approve_loss=payload.approve,reason=payload.reject_reason or ('Approved damage/loss' if payload.approve else 'Damage review rejected'),version=payload.version))
    return result

@router.get('/repairs/{repair_id}/warranty')
def repair_warranty(repair_id:str,user:User=Depends(require_permission('REPAIR_CREATE')),db:Session=Depends(db_session)):
    row=db.scalar(select(RepairWarranty).join(Repair, Repair.id==RepairWarranty.repair_id).where(RepairWarranty.repair_id==repair_id, Repair.branch_id==user.branch_id))
    if not row: raise HTTPException(404,'Repair warranty not found')
    status=warranty_status(row.start_date,row.expiry_date,date.today())
    if row.status != status and status in {'ACTIVE','EXPIRED'}:
        row.status=status; db.commit()
    return {'repair_warranty_id':str(row.id),'repair_id':str(row.repair_id),'start_date':row.start_date,'expiry_date':row.expiry_date,'warranty_period':row.warranty_period,'status':status}

@router.get('/repairs', dependencies=[Depends(require_permission('REPAIR_CREATE'))])
def repair_list(user:User=Depends(require_permission('REPAIR_CREATE')),db:Session=Depends(db_session)):
    from app.models.sales import Repair, RepairPayment
    from decimal import Decimal
    rows=db.scalars(select(Repair).where(Repair.branch_id==user.branch_id).order_by(Repair.date_in.desc()).limit(100)).all()
    out=[]
    for r in rows:
        paid=db.scalar(select(__import__('sqlalchemy', fromlist=['func']).func.coalesce(__import__('sqlalchemy', fromlist=['func']).func.sum(RepairPayment.amount),0)).where(RepairPayment.repair_id==r.id)) or 0
        outstanding = max(Decimal('0'), Decimal(r.final_amount or 0) - Decimal(paid))
        out.append({'repair_id':str(r.id),'repair_no':r.repair_no,'status':r.status,'device_brand':r.device_brand,'model':r.model,'customer_name':r.customer_name,'contact_no':r.contact_no,'date_in':r.date_in,'total_amount':r.total_amount,'final_amount':r.final_amount,'outstanding':outstanding})
    return out

@router.get('/day/status', response_model=DayStatusOut, dependencies=[Depends(require_permission('DAY_MANAGE'))])
def day_status(user:User=Depends(require_permission('DAY_MANAGE')),db:Session=Depends(db_session)):
    from datetime import date as dt_date
    row=DayFinanceService(db)._open(user.branch_id,dt_date.today())
    if not row:
        return DayStatusOut(day_session_id=None,business_date=dt_date.today(),status='NOT_STARTED',opening_cash=0)
    expected=DayFinanceService(db).expected_cash(row)
    return DayStatusOut(day_session_id=row.id,business_date=row.business_date,status=row.status,opening_cash=row.opening_cash,expected_cash=expected,version=row.version)
