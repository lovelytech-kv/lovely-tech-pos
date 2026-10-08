from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.fifo.engine import FifoEngine
from app.models.master import Item, WarrantyDefault
from app.models.sales import Payment, Sale, SaleLine
from app.models.security import AuditLog, DocumentEvent, IdempotencyKey
from app.models.warranty import ProductWarranty
from app.models.inventory import SerializedUnit
from app.services.numbering import NumberingService

CENT = Decimal("0.01")
QTY_PLACES = Decimal("0.001")
ZERO = Decimal("0")


class SaleValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SaleLineInput:
    item_id: uuid.UUID
    quantity: Decimal
    unit_price: Decimal | None = None
    discount: Decimal = ZERO
    serialized_unit_id: uuid.UUID | None = None
    warranty_type: str | None = None
    warranty_duration_value: int | None = None
    warranty_custom_rule: str | None = None


@dataclass(frozen=True)
class PaymentInput:
    method: str
    amount: Decimal
    reference: str | None = None


@dataclass(frozen=True)
class SaleRequest:
    branch_id: uuid.UUID
    cashier_id: uuid.UUID
    lines: tuple[SaleLineInput, ...]
    payments: tuple[PaymentInput, ...]
    document_type: str = "SYSTEM_PRINTED"
    manual_invoice_ref: str | None = None
    customer_id: uuid.UUID | None = None
    sale_datetime: datetime | None = None
    idempotency_key: str | None = None
    request_hash: str | None = None
    credit_sale: bool = False
    cash_received: Decimal | None = None
    discount_limit_percent: Decimal | None = None
    admin_discount_approved: bool = False


@dataclass(frozen=True)
class SaleResult:
    sale_id: uuid.UUID
    invoice_no: str
    grand_total: Decimal
    total_cost: Decimal
    negative_stock: bool
    version: int = 1
    warranty_ids: tuple[uuid.UUID, ...] = field(default_factory=tuple)
    replayed: bool = False


class SaleService:
    """Completes a sale inside the caller's DB transaction.

    The API layer must wrap the call in one database transaction. This service
    never commits partial sale effects: sale rows, payments, FIFO movements,
    serialized status, warranties, audit and document events are all flushed
    into the same transaction.
    """

    ALLOWED_DOCUMENT_TYPES = {"SYSTEM_PRINTED", "MANUAL", "NO_PRINT"}
    ALLOWED_PAYMENT_METHODS = {"CASH", "CARD", "ONLINE"}

    def __init__(self, session: Session):
        self.session = session
        self.fifo = FifoEngine(session)

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)

    @classmethod
    def validate_request(cls, request: SaleRequest) -> None:
        if not request.lines:
            raise SaleValidationError("Sale must contain at least one line")
        if not request.payments and not request.credit_sale:
            raise SaleValidationError("A completed sale requires payment unless it is an Admin credit sale")
        if request.credit_sale and not request.customer_id:
            raise SaleValidationError("Credit sale requires a customer")
        if request.cash_received is not None and request.cash_received < ZERO:
            raise SaleValidationError("Cash received cannot be negative")
        if request.document_type not in cls.ALLOWED_DOCUMENT_TYPES:
            raise SaleValidationError("Invalid document type")
        if request.document_type == "MANUAL" and not request.manual_invoice_ref:
            raise SaleValidationError("Manual invoice reference is required")
        if request.document_type != "MANUAL" and request.manual_invoice_ref:
            raise SaleValidationError("Manual invoice reference is only valid for MANUAL documents")

        for line in request.lines:
            if line.quantity <= ZERO:
                raise SaleValidationError("Sale quantity must be greater than zero")
            if line.discount < ZERO:
                raise SaleValidationError("Discount cannot be negative")
            if line.unit_price is not None and line.unit_price < ZERO:
                raise SaleValidationError("Sale price cannot be negative")
            if line.serialized_unit_id is not None and line.quantity != Decimal("1"):
                raise SaleValidationError("A serialized sale line must have quantity 1")
            if line.warranty_type is not None:
                wt = line.warranty_type.strip().upper()
                if wt not in {"NONE", "DAYS", "MONTHS", "CHECKING ONLY", "CUSTOM"}:
                    raise SaleValidationError("Unsupported sale-time warranty type")
                if wt in {"NONE", "CHECKING ONLY"} and (line.warranty_duration_value is not None or (line.warranty_custom_rule or '').strip()):
                    raise SaleValidationError("This warranty override cannot have duration/custom rule")
                if wt in {"DAYS", "MONTHS"} and line.warranty_duration_value is None:
                    raise SaleValidationError("Warranty override duration is required")
                if wt == "CUSTOM" and not (line.warranty_custom_rule or '').strip():
                    raise SaleValidationError("Custom warranty rule is required")

        if request.discount_limit_percent is not None and not request.admin_discount_approved:
            subtotal = sum((Decimal(x.unit_price or 0) * Decimal(x.quantity) for x in request.lines), ZERO)
            discount = sum((Decimal(x.discount) for x in request.lines), ZERO)
            if subtotal > ZERO:
                pct = (discount / subtotal) * Decimal("100")
                if pct > Decimal(request.discount_limit_percent):
                    raise SaleValidationError(f"Discount limit exceeded ({pct.quantize(Decimal('0.01'))}% > {Decimal(request.discount_limit_percent).quantize(Decimal('0.01'))}%). Admin approval required.")

        for payment in request.payments:
            if payment.method.upper() not in cls.ALLOWED_PAYMENT_METHODS:
                raise SaleValidationError(f"Unsupported payment method: {payment.method}")
            if payment.amount <= ZERO:
                raise SaleValidationError("Payment amount must be greater than zero")

    @staticmethod
    def canonical_request_hash(request: SaleRequest) -> str:
        payload = {
            "branch_id": str(request.branch_id),
            "cashier_id": str(request.cashier_id),
            "document_type": request.document_type,
            "manual_invoice_ref": request.manual_invoice_ref,
            "customer_id": str(request.customer_id) if request.customer_id else None,
            "sale_datetime": request.sale_datetime.isoformat() if request.sale_datetime else None,
            "lines": [
                {
                    "item_id": str(x.item_id),
                    "quantity": str(x.quantity),
                    "unit_price": str(x.unit_price) if x.unit_price is not None else None,
                    "discount": str(x.discount),
                    "serialized_unit_id": str(x.serialized_unit_id) if x.serialized_unit_id else None,
                    "warranty_type": x.warranty_type,
                    "warranty_duration_value": x.warranty_duration_value,
                    "warranty_custom_rule": x.warranty_custom_rule,
                }
                for x in request.lines
            ],
            "credit_sale": request.credit_sale,
            "payments": [
                {"method": x.method.upper(), "amount": str(x.amount), "reference": x.reference}
                for x in request.payments
            ],
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()

    def _get_idempotent_replay(self, request: SaleRequest, request_hash: str) -> SaleResult | None:
        if not request.idempotency_key:
            return None
        key = self.session.scalar(
            select(IdempotencyKey).where(IdempotencyKey.key == request.idempotency_key).with_for_update()
        )
        if key is None:
            return None
        if key.request_hash != request_hash:
            raise SaleValidationError("Idempotency key was already used for a different request")
        if not key.completed_at or not key.response_json:
            raise SaleValidationError("The same request is currently being completed; retry after transaction finishes")
        response = key.response_json
        return SaleResult(
            sale_id=uuid.UUID(response["sale_id"]),
            invoice_no=response["invoice_no"],
            grand_total=Decimal(response["grand_total"]),
            total_cost=Decimal(response["total_cost"]),
            negative_stock=bool(response["negative_stock"]),
            version=int(response.get("version", 1)),
            warranty_ids=tuple(uuid.UUID(x) for x in response.get("warranty_ids", [])),
            replayed=True,
        )

    def _reserve_idempotency(self, request: SaleRequest, request_hash: str) -> None:
        if not request.idempotency_key:
            return
        row = IdempotencyKey(
            key=request.idempotency_key,
            user_id=request.cashier_id,
            request_hash=request_hash,
            created_at=datetime.now(timezone.utc),
        )
        try:
            with self.session.begin_nested():
                self.session.add(row)
                self.session.flush()
        except IntegrityError:
            existing = self.session.scalar(
                select(IdempotencyKey).where(IdempotencyKey.key == request.idempotency_key).with_for_update()
            )
            if existing is None or existing.request_hash != request_hash:
                raise SaleValidationError("Idempotency key conflict")
            if existing.completed_at and existing.response_json:
                raise SaleValidationError("Idempotency request has already completed")

    def _lock_item(self, item_id: uuid.UUID) -> Item:
        item = self.session.scalar(select(Item).where(Item.id == item_id).with_for_update())
        if item is None or not item.is_active:
            raise SaleValidationError("Item is not available")
        return item

    def _resolve_price(self, line: SaleLineInput, item: Item) -> Decimal:
        price = line.unit_price if line.unit_price is not None else item.master_sale_price
        if price is None:
            raise SaleValidationError(f"Sale price is required for item {item.item_code}")
        return self._money(price)

    def _create_warranty(self, *, branch_id: uuid.UUID, sale_line: SaleLine, item: Item, sale_date: date, serialized_unit_id: uuid.UUID | None,
                         warranty_type: str | None = None, warranty_duration_value: int | None = None, warranty_custom_rule: str | None = None) -> ProductWarranty | None:
        default = self.session.scalar(
            select(WarrantyDefault)
            .where(WarrantyDefault.item_id == item.id, WarrantyDefault.is_active.is_(True))
            .order_by(WarrantyDefault.created_at.desc())
        )
        if warranty_type is None:
            if default is None:
                return None
            warranty_type, warranty_duration_value, warranty_custom_rule = default.warranty_type, default.duration_value, default.custom_rule
        else:
            warranty_type = warranty_type.strip().upper()
            if warranty_type not in {"NONE", "DAYS", "MONTHS", "CHECKING ONLY", "CUSTOM"}:
                raise SaleValidationError("Unsupported sale-time warranty type")
            if warranty_type in {"NONE", "CHECKING ONLY"} and (warranty_duration_value is not None or (warranty_custom_rule or '').strip()):
                raise SaleValidationError("This warranty override cannot have duration/custom rule")
            if warranty_type in {"DAYS", "MONTHS"} and warranty_duration_value is None:
                raise SaleValidationError("Warranty override duration is required")
            if warranty_type == "CUSTOM" and not (warranty_custom_rule or '').strip():
                raise SaleValidationError("Custom warranty rule is required")
        from app.services.warranty_calculator import calculate_expiry, WarrantyCalculationError
        try:
            expiry = calculate_expiry(sale_date, warranty_type, warranty_duration_value, warranty_custom_rule)
        except WarrantyCalculationError as exc:
            raise SaleValidationError(str(exc)) from exc
        warranty = ProductWarranty(
            branch_id=branch_id, sale_line_id=sale_line.id, serialized_unit_id=serialized_unit_id,
            warranty_no=NumberingService.next_number(self.session, "WAR", str(branch_id)),
            start_date=sale_date, expiry_date=expiry, warranty_type=warranty_type,
            duration_value=warranty_duration_value, custom_rule=warranty_custom_rule,
            source="SALE", status="ACTIVE",
        )
        self.session.add(warranty); self.session.flush(); return warranty

    def complete(self, request: SaleRequest, *, version: int | None = None) -> SaleResult:
        self.validate_request(request)
        request_hash = request.request_hash or self.canonical_request_hash(request)

        replay = self._get_idempotent_replay(request, request_hash)
        if replay is not None:
            return replay
        self._reserve_idempotency(request, request_hash)

        now = request.sale_datetime or datetime.now(timezone.utc)
        invoice_no = NumberingService.next_number(self.session, "INV", str(request.branch_id))
        sale = Sale(
            branch_id=request.branch_id,
            invoice_no=invoice_no,
            customer_id=request.customer_id,
            sale_datetime=now,
            cashier_id=request.cashier_id,
            document_type=request.document_type,
            manual_invoice_ref=request.manual_invoice_ref,
            subtotal=ZERO,
            discount_total=ZERO,
            grand_total=ZERO,
            status="DRAFT",
        )
        self.session.add(sale)
        self.session.flush()
        if version is not None and sale.version != version:
            raise SaleValidationError("Sale changed; reload before editing")

        subtotal = ZERO
        discount_total = ZERO
        grand_total = ZERO
        total_cost = ZERO
        negative_stock = False
        warranties: list[uuid.UUID] = []

        for input_line in request.lines:
            item = self._lock_item(input_line.item_id)
            price = self._resolve_price(input_line, item)
            gross = self._money(price * input_line.quantity)
            discount = self._money(input_line.discount)
            if discount > gross:
                raise SaleValidationError(f"Discount exceeds line total for item {item.item_code}")
            final_total = self._money(gross - discount)

            serialized = None
            if input_line.serialized_unit_id:
                serialized = self.session.scalar(
                    select(SerializedUnit)
                    .where(SerializedUnit.id == input_line.serialized_unit_id)
                    .with_for_update()
                )
                if serialized is None or serialized.branch_id != request.branch_id or serialized.item_id != item.id or serialized.status != "IN_STOCK":
                    raise SaleValidationError("Serialized/IMEI unit is not available for this sale")

            line = SaleLine(
                sale_id=sale.id,
                item_id=item.id,
                serialized_unit_id=input_line.serialized_unit_id,
                quantity=input_line.quantity,
                unit_price=price,
                discount=discount,
                final_total=final_total,
            )
            self.session.add(line)
            self.session.flush()

            allocation = self.fifo.consume(
                branch_id=request.branch_id,
                item_id=item.id,
                quantity=input_line.quantity,
                source_type="SALE",
                source_id=line.id,
                occurred_at=now,
                reason=f"Invoice {invoice_no}",
            )
            total_cost += allocation.total_cost
            negative_stock = negative_stock or allocation.negative_quantity > ZERO

            if serialized:
                serialized.status = "SOLD"
            warranty = self._create_warranty(
                branch_id=request.branch_id,
                sale_line=line,
                item=item,
                sale_date=now.date(),
                serialized_unit_id=input_line.serialized_unit_id,
                warranty_type=input_line.warranty_type,
                warranty_duration_value=input_line.warranty_duration_value,
                warranty_custom_rule=input_line.warranty_custom_rule,
            )
            if warranty:
                warranties.append(warranty.id)

            subtotal += gross
            discount_total += discount
            grand_total += final_total

        subtotal = self._money(subtotal)
        discount_total = self._money(discount_total)
        grand_total = self._money(grand_total)
        payment_total = self._money(sum((p.amount for p in request.payments), ZERO))
        cash_component = self._money(sum((p.amount for p in request.payments if p.method.upper() == "CASH"), ZERO))
        if request.credit_sale:
            if payment_total != ZERO:
                raise SaleValidationError("Credit sale cannot include immediate payment")
        else:
            if payment_total != grand_total:
                raise SaleValidationError(f"Payment total {payment_total} does not match sale total {grand_total}")
            if request.cash_received is not None and request.cash_received < cash_component:
                raise SaleValidationError(f"Cash received {request.cash_received} is less than the cash payment {cash_component}")
            if request.cash_received is not None and cash_component == ZERO and request.cash_received > ZERO:
                raise SaleValidationError("Cash received cannot be entered when the sale has no cash payment")

        if request.discount_limit_percent is not None and not request.admin_discount_approved and subtotal > ZERO:
            pct = (discount_total / subtotal) * Decimal("100")
            if pct > Decimal(request.discount_limit_percent):
                raise SaleValidationError(f"Discount limit exceeded ({pct.quantize(Decimal('0.01'))}% > {Decimal(request.discount_limit_percent).quantize(Decimal('0.01'))}%). Admin approval required.")

        sale.subtotal = subtotal
        sale.discount_total = discount_total
        sale.grand_total = grand_total
        sale.total_cost = self._money(total_cost)
        sale.status = "COMPLETED"

        for payment_input in request.payments:
            self.session.add(
                Payment(
                    sale_id=sale.id,
                    payment_method=payment_input.method.upper(),
                    amount=self._money(payment_input.amount),
                    payment_datetime=now,
                    reference=payment_input.reference,
                )
            )

        audit = AuditLog(
            branch_id=request.branch_id,
            actor_user_id=request.cashier_id,
            action_type="SALE_COMPLETED",
            entity_type="SALE",
            entity_id=sale.id,
            timestamp=now,
            after_json={
                "invoice_no": invoice_no,
                "subtotal": str(subtotal),
                "discount_total": str(discount_total),
                "grand_total": str(grand_total),
                "total_cost": str(total_cost),
                "negative_stock": negative_stock,
            },
            source_transaction_id=sale.id,
        )
        self.session.add(audit)
        self.session.add(
            DocumentEvent(
                document_type="SALE",
                document_id=sale.id,
                event_type="ORIGINAL",
                actor_user_id=request.cashier_id,
                occurred_at=now,
                reason="Sale completed",
            )
        )

        if request.idempotency_key:
            idem = self.session.scalar(
                select(IdempotencyKey).where(IdempotencyKey.key == request.idempotency_key).with_for_update()
            )
            if idem is not None:
                idem.response_json = {
                    "sale_id": str(sale.id),
                    "invoice_no": invoice_no,
                    "grand_total": str(grand_total),
                    "total_cost": str(total_cost),
                    "negative_stock": negative_stock,
                    "version": sale.version,
                    "warranty_ids": [str(x) for x in warranties],
                }
                idem.completed_at = datetime.now(timezone.utc)

        sale.version += 1
        self.session.flush()
        return SaleResult(
            sale_id=sale.id,
            invoice_no=invoice_no,
            grand_total=grand_total,
            total_cost=total_cost,
            negative_stock=negative_stock,
            version=sale.version,
            warranty_ids=tuple(warranties),
        )
