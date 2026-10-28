from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import db_session, require_permission
from app.models.master import User
from app.schemas.api import ReturnIn, ExchangeIn, ReturnPaymentIn
from app.services.returns import ReturnService, ReturnRequest, ReturnLineInput, ExchangeService, ExchangeRequest, ReturnValidationError

router = APIRouter(prefix="/returns", tags=["returns"])

@router.post("")
def create_return(payload: ReturnIn, user: User = Depends(require_permission("RETURN_CREATE")), db: Session = Depends(db_session)):
    try:
        result = ReturnService(db).complete(
            ReturnRequest(
                branch_id=user.branch_id, cashier_id=user.id, original_sale_id=payload.original_sale_id,
                lines=tuple(ReturnLineInput(**x.model_dump()) for x in payload.lines), return_charge=payload.return_charge,
                reason=payload.reason, return_datetime=payload.return_datetime,
                admin_override=bool(payload.admin_override and user.role.code.upper() == "ADMIN"),
                idempotency_key=payload.idempotency_key,
            ),
            version=payload.version,
        )
        db.commit()
        return {"return_id": str(result.return_id), "return_no": result.return_no, "refund_total": result.refund_total, "return_charge": result.return_charge, "version": result.version}
    except ReturnValidationError as exc:
        db.rollback(); raise HTTPException(400, str(exc))

@router.post("/exchange")
def create_exchange(payload: ExchangeIn, user: User = Depends(require_permission("RETURN_CREATE")), db: Session = Depends(db_session)):
    try:
        result = ExchangeService(db).complete(ExchangeRequest(branch_id=user.branch_id, cashier_id=user.id, return_id=payload.return_id, replacement_sale_id=payload.replacement_sale_id, exchange_datetime=payload.exchange_datetime, version=payload.version))
        db.commit()
        return {"exchange_id": str(result.exchange_id), "exchange_no": result.exchange_no, "difference_amount": result.difference_amount}
    except ReturnValidationError as exc:
        db.rollback(); raise HTTPException(400, str(exc))

@router.post("/{return_id}/refund-payment")
def refund_payment(return_id: str, payload: ReturnPaymentIn, user: User = Depends(require_permission("RETURN_CREATE")), db: Session = Depends(db_session)):
    try:
        row = ReturnService(db).record_refund_payment(return_id=return_id, branch_id=user.branch_id, actor_user_id=user.id, payment_method=payload.payment_method, amount=payload.amount, payment_datetime=payload.payment_datetime, reference=payload.reference, idempotency_key=payload.idempotency_key)
        db.commit()
        service = ReturnService(db)
        paid = service.refund_paid_total(row.return_id)
        return {"return_id": str(row.return_id), "payment_id": str(row.id), "paid_total": paid, "payment_method": row.payment_method, "amount": row.amount}
    except ReturnValidationError as exc:
        db.rollback(); raise HTTPException(400, str(exc))


@router.get('/{return_id}')
def get_return(return_id: str, user: User = Depends(require_permission('RETURN_CREATE')), db: Session = Depends(db_session)):
    from sqlalchemy import func, select
    from app.models.sales import Return, ReturnLine, ReturnPayment
    from app.models.master import Item
    ret = db.scalar(select(Return).where(Return.id == return_id, Return.branch_id == user.branch_id))
    if ret is None:
        raise HTTPException(404, 'Return not found')
    lines = db.execute(select(ReturnLine, Item).join(Item, Item.id == ReturnLine.item_id).where(ReturnLine.return_id == ret.id)).all()
    paid = db.scalar(select(func.coalesce(func.sum(ReturnPayment.amount), 0)).where(ReturnPayment.return_id == ret.id)) or 0
    return {
        'return_id': str(ret.id), 'return_no': ret.return_no, 'original_sale_id': str(ret.original_sale_id),
        'return_datetime': ret.return_datetime, 'refund_total': ret.refund_total, 'return_charge': ret.return_charge,
        'status': ret.status, 'reason': ret.reason, 'version': ret.version, 'paid_total': paid,
        'remaining_refund': max(Decimal('0'), Decimal(ret.refund_total) - Decimal(paid)),
        'lines': [{'return_line_id': str(line.id), 'item_id': str(line.item_id), 'item_code': item.item_code,
                   'description': item.description, 'quantity': line.quantity, 'refund_amount': line.refund_amount,
                   'condition': line.condition} for line, item in lines]
    }

@router.get('/{return_id}/refund-payments')
def return_refund_payments(return_id: str, user: User = Depends(require_permission('RETURN_CREATE')), db: Session = Depends(db_session)):
    from sqlalchemy import select
    from app.models.sales import ReturnPayment, Return
    ret = db.scalar(select(Return).where(Return.id == return_id, Return.branch_id == user.branch_id))
    if ret is None:
        raise HTTPException(404, 'Return not found')
    rows = db.scalars(select(ReturnPayment).where(ReturnPayment.return_id == ret.id).order_by(ReturnPayment.payment_datetime)).all()
    return [{'payment_id': str(x.id), 'payment_method': x.payment_method, 'amount': x.amount, 'payment_datetime': x.payment_datetime, 'reference': x.reference} for x in rows]

