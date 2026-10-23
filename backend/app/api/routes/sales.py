import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal
from app.api.deps import db_session, require_permission
from app.models.master import User
from app.models.sales import Sale, SaleLine
from app.models.master import Item
from sqlalchemy import select
from app.schemas.api import SaleIn, SaleOut
from app.services.sales import SaleService, SaleRequest, SaleLineInput, PaymentInput, SaleValidationError
from app.services.approvals import ApprovalService
from app.models.security import ApprovalRequest
from fastapi.encoders import jsonable_encoder

router = APIRouter(prefix="/sales", tags=["sales"])

@router.post("", response_model=SaleOut)
def create_sale(payload: SaleIn, user: User = Depends(require_permission("SALE_CREATE")), db: Session = Depends(db_session)):
    if payload.credit_sale and user.role.code.upper() != "ADMIN":
        raise HTTPException(403, "Credit sale is Admin-only")
    sale_datetime = payload.sale_datetime
    if sale_datetime is not None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if sale_datetime > now:
            raise HTTPException(400, "Sale date/time cannot be in the future")
        # Backdated/missed sales are deliberately explicit and admin-only.
        if sale_datetime.date() != now.date() and user.role.code.upper() != "ADMIN":
            raise HTTPException(403, "Backdated or missed sale entry is Admin-only")
    approval_ok = False
    if payload.admin_discount_approval_id:
        approval = db.scalar(select(ApprovalRequest).where(ApprovalRequest.id == payload.admin_discount_approval_id, ApprovalRequest.branch_id == user.branch_id, ApprovalRequest.action_type == "DISCOUNT_OVERRIDE", ApprovalRequest.status == "APPROVED"))
        if not approval:
            raise HTTPException(400, "Approved discount authorization not found")
        approval_ok = True
    req = SaleRequest(branch_id=user.branch_id, cashier_id=user.id, lines=tuple(SaleLineInput(**x.model_dump()) for x in payload.lines), payments=tuple(PaymentInput(**x.model_dump()) for x in payload.payments), document_type=payload.document_type, manual_invoice_ref=payload.manual_invoice_ref, customer_id=payload.customer_id, sale_datetime=sale_datetime, idempotency_key=payload.idempotency_key, credit_sale=payload.credit_sale, cash_received=payload.cash_received, discount_limit_percent=user.discount_limit_percent if user.role.code.upper() != "ADMIN" else None, admin_discount_approved=approval_ok or user.role.code.upper() == "ADMIN")
    try:
        result = SaleService(db).complete(req, version=payload.version)
        db.commit()
    except SaleValidationError as exc:
        db.rollback(); raise HTTPException(400, str(exc))
    except Exception:
        db.rollback(); raise
    cash_due = sum((p.amount for p in req.payments if p.method.upper() == "CASH"), Decimal("0"))
    change = Decimal("0")
    if req.cash_received is not None and req.cash_received >= cash_due:
        change = (req.cash_received - cash_due).quantize(Decimal("0.01"))
    return SaleOut(sale_id=result.sale_id, invoice_no=result.invoice_no, grand_total=result.grand_total, change_amount=change, total_cost=result.total_cost if user.role.code.upper() == "ADMIN" else None, negative_stock=result.negative_stock, warranty_ids=list(result.warranty_ids), replayed=result.replayed, version=result.version)


@router.post("/discount-approval")
def request_discount_approval(payload: SaleIn, user: User = Depends(require_permission("APPROVAL_REQUEST")), db: Session = Depends(db_session)):
    if user.role.code.upper() == "ADMIN":
        raise HTTPException(400, "Admin does not need a discount approval")
    subtotal = sum((Decimal(x.unit_price or 0) * x.quantity for x in payload.lines), Decimal("0"))
    discount = sum((x.discount for x in payload.lines), Decimal("0"))
    pct = (discount / subtotal * Decimal("100")) if subtotal else Decimal("0")
    if pct <= Decimal(user.discount_limit_percent):
        raise HTTPException(400, "Sale is within the configured discount limit; normal sale endpoint should be used")
    encoded = jsonable_encoder(payload.model_dump())
    req = ApprovalService(db).request(branch_id=user.branch_id, requester_user_id=user.id, action_type="DISCOUNT_OVERRIDE", payload={"sale": encoded, "cashier_id": str(user.id), "discount_percent": str(pct)})
    db.commit()
    return {"approval_id": str(req.id), "status": req.status, "approval_action_id": req.approval_action_id, "discount_percent": pct}


@router.get("/{sale_id}")
def get_sale_detail(sale_id: str, user: User = Depends(require_permission("RETURN_CREATE")), db: Session = Depends(db_session)):
    # The Returns screen accepts either the sale id or the printed invoice number (e.g. INV-000013).
    key = sale_id.strip()
    try:
        match = Sale.id == uuid.UUID(key)
    except ValueError:
        match = Sale.invoice_no == key.upper()
    sale = db.scalar(select(Sale).where(match, Sale.branch_id == user.branch_id, Sale.status == "COMPLETED"))
    if sale is None:
        raise HTTPException(404, "Sale not found")
    lines = db.execute(select(SaleLine, Item).join(Item, Item.id == SaleLine.item_id).where(SaleLine.sale_id == sale.id)).all()
    return {
        "sale_id": str(sale.id), "invoice_no": sale.invoice_no, "sale_datetime": sale.sale_datetime,
        "grand_total": sale.grand_total,
        "lines": [{"sale_line_id": str(line.id), "item_id": str(line.item_id), "item_code": item.item_code,
                   "description": item.description, "quantity": line.quantity, "unit_price": line.unit_price,
                   "discount": line.discount, "final_total": line.final_total,
                   "serialized_unit_id": str(line.serialized_unit_id) if line.serialized_unit_id else None}
                  for line, item in lines]
    }
