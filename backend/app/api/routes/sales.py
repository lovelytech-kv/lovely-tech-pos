import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.models.master import Item, User
from app.models.sales import Customer, Payment, Sale, SaleLine
from app.models.security import ApprovalRequest
from app.schemas.api import SaleIn, SaleOut
from app.services.sales import (
    PaymentInput,
    SaleLineInput,
    SaleRequest,
    SaleService,
    SaleValidationError,
)
from app.services.approvals import ApprovalService
from fastapi.encoders import jsonable_encoder

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("")
def list_sales(
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    cashier_id: uuid.UUID | None = None,
    payment_method: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(require_permission("SALE_CREATE")),
    db: Session = Depends(db_session),
):
    """
    List sales (paginated, filterable).

    Admin sees all sales in the branch. Cashier sees only their own sales.
    Default date range is today if neither date_from nor date_to is provided.
    """
    # Clamp pagination
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))

    # Default date range to today if neither is set
    if date_from is None and date_to is None:
        today_local = datetime.now(timezone.utc).date()
        date_from = today_local
        date_to = today_local

    stmt = select(Sale).where(Sale.branch_id == user.branch_id)

    if date_from is not None:
        stmt = stmt.where(
            Sale.sale_datetime >= datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        )
    if date_to is not None:
        stmt = stmt.where(
            Sale.sale_datetime
            < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        )

    if status:
        stmt = stmt.where(Sale.status == status.strip().upper())

    is_admin = user.role.code.upper() == "ADMIN"
    if not is_admin:
        # Cashier restricted to own sales
        stmt = stmt.where(Sale.cashier_id == user.id)
    elif cashier_id is not None:
        stmt = stmt.where(Sale.cashier_id == cashier_id)

    if payment_method:
        stmt = stmt.where(
            Sale.id.in_(
                select(Payment.sale_id).where(
                    Payment.payment_method == payment_method.strip().upper()
                )
            )
        )

    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Sale.invoice_no.ilike(like),
                Sale.id.in_(
                    select(SaleLine.sale_id)
                    .join(Item, Item.id == SaleLine.item_id)
                    .where(
                        or_(
                            Item.item_code.ilike(like),
                            Item.description.ilike(like),
                        )
                    )
                ),
                Sale.customer_id.in_(
                    select(Customer.id).where(
                        or_(
                            Customer.name.ilike(like),
                            Customer.contact_no.ilike(like),
                        )
                    )
                ),
            )
        )

    # Total count for pagination
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    rows = (
        db.execute(stmt.order_by(Sale.sale_datetime.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )

    if not rows:
        return {"items": [], "total": int(total), "has_more": False}

    sale_ids = [r.id for r in rows]

    # Cashier display names
    cashier_ids = {r.cashier_id for r in rows}
    cashiers = db.scalars(select(User).where(User.id.in_(cashier_ids))).all()
    cashier_map = {u.id: u for u in cashiers}

    # Customer info
    customer_ids = {r.customer_id for r in rows if r.customer_id}
    if customer_ids:
        customers = db.scalars(select(Customer).where(Customer.id.in_(customer_ids))).all()
        customer_map = {c.id: c for c in customers}
    else:
        customer_map = {}

    # Item count per sale (sum of quantities)
    qty_rows = db.execute(
        select(SaleLine.sale_id, func.sum(SaleLine.quantity))
        .where(SaleLine.sale_id.in_(sale_ids))
        .group_by(SaleLine.sale_id)
    ).all()
    item_count_map = {sid: qty for sid, qty in qty_rows}

    # Payment methods per sale
    pay_rows = db.execute(
        select(Payment.sale_id, Payment.payment_method)
        .where(Payment.sale_id.in_(sale_ids))
        .distinct()
    ).all()
    payment_methods_map: dict = {}
    for sid, method in pay_rows:
        payment_methods_map.setdefault(sid, set()).add(method)

    label_map = {"CASH": "Cash", "CARD": "Card", "ONLINE": "Online"}

    items = []
    for s in rows:
        methods = payment_methods_map.get(s.id, set())
        if not methods:
            payment_summary = "Credit"
        else:
            ordered = [m for m in ["CASH", "CARD", "ONLINE"] if m in methods]
            others = [m for m in methods if m not in ordered]
            payment_summary = " + ".join(label_map.get(m, m.title()) for m in ordered + others)

        raw_count = item_count_map.get(s.id)
        if raw_count is None:
            item_count: int | float = 0
        else:
            as_int = int(raw_count) if Decimal(raw_count) == Decimal(raw_count).to_integral_value() else None
            item_count = as_int if as_int is not None else float(raw_count)

        customer = customer_map.get(s.customer_id) if s.customer_id else None
        cashier = cashier_map.get(s.cashier_id)

        items.append(
            {
                "sale_id": str(s.id),
                "invoice_no": s.invoice_no,
                "sale_datetime": s.sale_datetime,
                "customer_name": customer.name if customer else None,
                "customer_contact": customer.contact_no if customer else None,
                "item_count": item_count,
                "grand_total": str(s.grand_total),
                "payment_summary": payment_summary,
                "cashier_name": cashier.display_name if cashier else "—",
                "cashier_id": str(s.cashier_id),
                "status": s.status,
                "is_voided": s.status == "VOIDED",
            }
        )

    return {
        "items": items,
        "total": int(total),
        "has_more": (offset + len(items)) < total,
    }


@router.post("", response_model=SaleOut)
def create_sale(payload: SaleIn, user: User = Depends(require_permission("SALE_CREATE")), db: Session = Depends(db_session)):
    if payload.credit_sale and user.role.code.upper() != "ADMIN":
        raise HTTPException(403, "Credit sale is Admin-only")
    sale_datetime = payload.sale_datetime
    if sale_datetime is not None:
        now = datetime.now(timezone.utc)
        if sale_datetime > now:
            raise HTTPException(400, "Sale date/time cannot be in the future")
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
        "grand_total": sale.grand_total, "version": sale.version,
        "lines": [{"sale_line_id": str(line.id), "item_id": str(line.item_id), "item_code": item.item_code,
                   "description": item.description, "quantity": line.quantity, "unit_price": line.unit_price,
                   "discount": line.discount, "final_total": line.final_total,
                   "serialized_unit_id": str(line.serialized_unit_id) if line.serialized_unit_id else None}
                  for line, item in lines]
    }


@router.post("/{sale_id}/void")
def void_sale(sale_id: uuid.UUID, reason: str, version: int | None = None, admin_password: str | None = None,
              user: User = Depends(require_permission("ADMIN_PANEL")), db: Session = Depends(db_session)):
    from app.security.reauth import require_admin_reauth
    from app.services.sale_void import SaleVoidError, SaleVoidService
    require_admin_reauth(user=user, password=admin_password, db=db, action="sale void")
    sale = db.scalar(select(Sale).where(Sale.id == sale_id, Sale.branch_id == user.branch_id).with_for_update())
    if sale is None:
        raise HTTPException(404, "Sale not found")
    try:
        SaleVoidService(db).void(sale=sale, reason=reason, actor_user_id=user.id, version=version)
        db.commit()
    except SaleVoidError as exc:
        db.rollback()
        raise HTTPException(409 if "version" in str(exc) else 400, str(exc))
    return {"sale_id": str(sale.id), "invoice_no": sale.invoice_no, "status": sale.status, "version": sale.version}