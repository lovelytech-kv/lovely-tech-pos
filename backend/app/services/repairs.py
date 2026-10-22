from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.fifo.engine import FifoEngine
from app.models.inventory import DamageLossRecord, FifoAllocation, PurchaseLot, StockMovement
from app.models.sales import Repair, RepairPart, RepairPayment, RepairWarranty
from app.models.security import AuditLog, DocumentEvent
from app.services.numbering import NumberingService
from app.services.warranty_calculator import calculate_expiry, WarrantyCalculationError

CENT = Decimal("0.01")
ZERO = Decimal("0")

class RepairValidationError(ValueError):
    pass

@dataclass(frozen=True)
class RepairCreateRequest:
    branch_id: uuid.UUID
    actor_user_id: uuid.UUID
    device_brand: str | None = None
    model: str | None = None
    given_accessories: str | None = None
    special_note: str | None = None
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    contact_no: str | None = None
    reported_fault: str | None = None
    estimated_amount: Decimal | None = None
    warranty_period: str | None = None
    date_in: datetime | None = None

@dataclass(frozen=True)
class RepairPartInput:
    item_id: uuid.UUID
    quantity: Decimal
    charge_amount: Decimal = ZERO
    notes: str | None = None

@dataclass(frozen=True)
class RepairPaymentInput:
    method: str
    amount: Decimal
    reference: str | None = None
    payment_type: str = "RECEIPT"

class RepairService:
    STATUSES = {"RECEIVED","CHECKING","WAITING FOR CUSTOMER","WAITING FOR PART","REPAIRING","READY","DELIVERED","RETURNED TO CUSTOMER","CANCELLED"}
    ALLOWED_TRANSITIONS = {
        "RECEIVED": {"CHECKING", "CANCELLED"},
        "CHECKING": {"WAITING FOR CUSTOMER", "WAITING FOR PART", "REPAIRING", "CANCELLED"},
        "WAITING FOR CUSTOMER": {"REPAIRING", "CANCELLED"},
        "WAITING FOR PART": {"REPAIRING", "CANCELLED"},
        "REPAIRING": {"WAITING FOR CUSTOMER", "WAITING FOR PART", "READY", "CANCELLED"},
        "READY": {"DELIVERED", "CANCELLED"},
        "DELIVERED": {"RETURNED TO CUSTOMER"},
        "RETURNED TO CUSTOMER": set(),
        "CANCELLED": set(),
    }
    ALLOWED_TRANSITIONS = {
        "RECEIVED": {"CHECKING", "CANCELLED"},
        "CHECKING": {"WAITING FOR CUSTOMER", "WAITING FOR PART", "REPAIRING", "CANCELLED"},
        "WAITING FOR CUSTOMER": {"CHECKING", "REPAIRING", "CANCELLED"},
        "WAITING FOR PART": {"REPAIRING", "CANCELLED"},
        "REPAIRING": {"WAITING FOR CUSTOMER", "WAITING FOR PART", "READY", "CANCELLED"},
        "READY": {"DELIVERED", "RETURNED TO CUSTOMER", "CANCELLED"},
        "DELIVERED": set(),
        "RETURNED TO CUSTOMER": set(),
        "CANCELLED": set(),
    }
    PAYMENT_METHODS = {"CASH","CARD","ONLINE"}

    def __init__(self, session: Session):
        self.session = session
        self.fifo = FifoEngine(session)

    @staticmethod
    def money(v: Decimal) -> Decimal:
        return Decimal(v).quantize(CENT, rounding=ROUND_HALF_UP)

    def create(self, req: RepairCreateRequest) -> Repair:
        now = req.date_in or datetime.now(timezone.utc)
        repair = Repair(
            branch_id=req.branch_id,
            repair_no=NumberingService.next_number(self.session, "REP", str(req.branch_id)),
            status="RECEIVED",
            device_brand=req.device_brand, model=req.model,
            given_accessories=req.given_accessories, special_note=req.special_note,
            customer_id=req.customer_id, customer_name=req.customer_name, contact_no=req.contact_no,
            date_in=now, reported_fault=req.reported_fault,
            estimated_amount=self.money(req.estimated_amount) if req.estimated_amount is not None else None,
            warranty_period=req.warranty_period,
        )
        self.session.add(repair); self.session.flush()
        self._audit(req.branch_id, req.actor_user_id, "REPAIR_CREATED", repair, now, {"repair_no": repair.repair_no})
        self.session.add(DocumentEvent(document_type="REPAIR", document_id=repair.id, event_type="ORIGINAL", actor_user_id=req.actor_user_id, occurred_at=now, reason="Repair created"))
        self.session.flush()
        return repair

    def set_status(self, repair_id: uuid.UUID, branch_id: uuid.UUID, actor_user_id: uuid.UUID, status: str, *, version: int | None = None, authorized_by: uuid.UUID | None = None) -> Repair:
        if status not in self.STATUSES:
            raise RepairValidationError("Invalid repair status")
        repair = self.session.scalar(select(Repair).where(Repair.id == repair_id, Repair.branch_id == branch_id).with_for_update())
        if repair is None: raise RepairValidationError("Repair not found")
        if version is not None and repair.version != version: raise RepairValidationError("Repair changed; reload before editing")
        if repair.status == "CANCELLED": raise RepairValidationError("Cancelled repair cannot change status")
        if status != repair.status and status not in self.ALLOWED_TRANSITIONS.get(repair.status, set()):
            raise RepairValidationError(f"Invalid repair status transition: {repair.status} -> {status}")
        repair.status = status
        repair.version += 1
        if authorized_by: repair.authorized_by = authorized_by
        self.session.add(AuditLog(branch_id=branch_id, actor_user_id=actor_user_id, action_type="REPAIR_STATUS_CHANGED", entity_type="REPAIR", entity_id=repair.id, timestamp=datetime.now(timezone.utc), after_json={"status": status}, source_transaction_id=repair.id))
        self.session.flush(); return repair

    def detail(self, repair_id: uuid.UUID, branch_id: uuid.UUID) -> dict:
        repair = self.session.scalar(select(Repair).where(Repair.id == repair_id, Repair.branch_id == branch_id))
        if repair is None:
            raise RepairValidationError("Repair not found")
        parts = self.session.scalars(select(RepairPart).where(RepairPart.repair_id == repair.id).order_by(RepairPart.created_at.asc())).all()
        payments = self.session.scalars(select(RepairPayment).where(RepairPayment.repair_id == repair.id).order_by(RepairPayment.payment_datetime.asc())).all()
        return {
            "repair_id": str(repair.id), "repair_no": repair.repair_no, "status": repair.status, "version": repair.version,
            "device_brand": repair.device_brand, "model": repair.model, "given_accessories": repair.given_accessories,
            "special_note": repair.special_note, "customer_name": repair.customer_name, "contact_no": repair.contact_no,
            "date_in": repair.date_in, "hand_over_date": repair.hand_over_date, "reported_fault": repair.reported_fault,
            "estimated_amount": repair.estimated_amount, "final_amount": repair.final_amount, "total_amount": repair.total_amount,
            "labour_amount": repair.labour_amount, "warranty_period": repair.warranty_period,
            "repair_invoice_ref": repair.repair_invoice_ref, "description_amount": repair.description_amount,
            "outstanding": self.outstanding(repair.id, branch_id),
            "parts": [{"id": str(x.id), "item_id": str(x.item_id), "quantity": x.quantity, "charge_amount": x.charge_amount, "fifo_cost": x.fifo_cost, "status": x.status, "notes": x.notes} for x in parts],
            "payments": [{"id": str(x.id), "method": x.payment_method, "amount": x.amount, "payment_datetime": x.payment_datetime, "reference": x.reference, "proof_no": x.proof_no, "payment_type": x.payment_type} for x in payments],
        }

    def add_part(self, repair_id: uuid.UUID, branch_id: uuid.UUID, actor_user_id: uuid.UUID, inp: RepairPartInput) -> RepairPart:
        if inp.quantity <= ZERO: raise RepairValidationError("Part quantity must be greater than zero")
        if inp.charge_amount < ZERO: raise RepairValidationError("Part charge cannot be negative")
        repair = self.session.scalar(select(Repair).where(Repair.id == repair_id, Repair.branch_id == branch_id).with_for_update())
        if repair is None or repair.status == "CANCELLED": raise RepairValidationError("Repair is not available")
        part_id = uuid.uuid4()
        allocation = self.fifo.consume(branch_id=branch_id, item_id=inp.item_id, quantity=inp.quantity, source_type="REPAIR_PART", source_id=part_id, occurred_at=datetime.now(timezone.utc), reason=f"Repair {repair.repair_no}")
        # stock_movement_id must reference the StockMovement row the FIFO engine actually created
        # (allocation.movement_id); a random uuid violated repair_parts_stock_movement_id_fkey (HTTP 500).
        part = RepairPart(id=part_id, repair_id=repair.id, item_id=inp.item_id, quantity=inp.quantity, charge_amount=self.money(inp.charge_amount), fifo_cost=self.money(allocation.total_cost), status="USED", stock_movement_id=allocation.movement_id, notes=inp.notes)
        self.session.add(part); self.session.flush()
        self._audit(branch_id, actor_user_id, "REPAIR_PART_USED", repair, datetime.now(timezone.utc), {"item_id": str(inp.item_id), "quantity": str(inp.quantity), "fifo_cost": str(part.fifo_cost)})
        return part


    def remove_part(self, repair_id: uuid.UUID, part_id: uuid.UUID, branch_id: uuid.UUID, actor_user_id: uuid.UUID, *, condition: str, reason: str) -> RepairPart:
        if condition not in {"GOOD", "DAMAGED"}:
            raise RepairValidationError("Condition must be GOOD or DAMAGED")
        if not reason.strip():
            raise RepairValidationError("Removal reason is required")
        repair = self.session.scalar(select(Repair).where(Repair.id==repair_id, Repair.branch_id==branch_id).with_for_update())
        part = self.session.scalar(select(RepairPart).where(RepairPart.id==part_id, RepairPart.repair_id==repair_id).with_for_update())
        if repair is None or part is None:
            raise RepairValidationError("Repair part not found")
        if part.status != "USED":
            raise RepairValidationError("Only currently used parts can be removed")
        now=datetime.now(timezone.utc)
        if condition == "GOOD":
            self._restore_part_if_good(part, branch_id, repair.id, now, actor_user_id)
        else:
            # The part has already been consumed from stock. Mark its loss for Admin review
            # without consuming stock a second time.
            movement = self.session.scalar(select(StockMovement).where(StockMovement.id==part.stock_movement_id).with_for_update()) if part.stock_movement_id else None
            loss=DamageLossRecord(branch_id=branch_id,item_id=part.item_id,quantity=part.quantity,reason=reason,source_type="REPAIR_PART_REMOVAL",source_id=part.id,approved_by=None,review_status="PENDING_ADMIN")
            self.session.add(loss)
            part.status="DAMAGED_REVIEW"
        self._audit(branch_id, actor_user_id, "REPAIR_PART_REMOVED", repair, now, {"part_id":str(part.id),"condition":condition,"reason":reason,"status":part.status})
        self.session.flush(); return part

    def review_damaged_part(self, part_id: uuid.UUID, branch_id: uuid.UUID, admin_user_id: uuid.UUID, *, approve_loss: bool, reason: str, version: int | None = None) -> dict:
        part=self.session.scalar(select(RepairPart).join(Repair).where(RepairPart.id==part_id,Repair.branch_id==branch_id).with_for_update())
        if not part or part.status != "DAMAGED_REVIEW": raise RepairValidationError("Damage review is not pending")
        loss=self.session.scalar(select(DamageLossRecord).where(DamageLossRecord.source_type=="REPAIR_PART_REMOVAL",DamageLossRecord.source_id==part.id,DamageLossRecord.review_status=="PENDING_ADMIN").with_for_update())
        if not loss: raise RepairValidationError("Damage review record not found")
        if version is None: raise RepairValidationError("Damage loss record version is required; reload before editing")
        if loss.version != version: raise RepairValidationError("Damage loss record changed; reload before editing")
        if approve_loss:
            loss.review_status="APPROVED"; loss.approved_by=admin_user_id; part.status="DAMAGED"
        else:
            loss.review_status="REJECTED"; part.status="USED"
        loss.version += 1
        self._audit(branch_id,admin_user_id,"REPAIR_PART_DAMAGE_REVIEWED",self.session.get(Repair,part.repair_id),datetime.now(timezone.utc),{"part_id":str(part.id),"approved":approve_loss,"reason":reason,"version":loss.version})
        self.session.flush(); return {"part_id":str(part.id),"status":part.status,"review_status":loss.review_status,"version":loss.version}

    def add_payment(self, repair_id: uuid.UUID, branch_id: uuid.UUID, actor_user_id: uuid.UUID, inp: RepairPaymentInput, idempotency_key: str | None = None) -> RepairPayment:
        method = inp.method.upper()
        if method not in self.PAYMENT_METHODS: raise RepairValidationError("Unsupported payment method")
        if inp.amount <= ZERO: raise RepairValidationError("Payment amount must be greater than zero")
        if idempotency_key:
            existing = self.session.scalar(select(RepairPayment).where(RepairPayment.idempotency_key == idempotency_key).with_for_update())
            if existing is not None:
                if existing.repair_id != repair_id or existing.payment_method != inp.method.upper() or self.money(existing.amount) != self.money(inp.amount) or existing.reference != inp.reference or existing.payment_type != inp.payment_type:
                    raise RepairValidationError("Idempotency key was already used for a different repair payment")
                return existing
        repair = self.session.scalar(select(Repair).where(Repair.id == repair_id, Repair.branch_id == branch_id).with_for_update())
        if repair is None: raise RepairValidationError("Repair not found")
        payment = RepairPayment(repair_id=repair.id, payment_method=method, amount=self.money(inp.amount), payment_datetime=datetime.now(timezone.utc), reference=inp.reference, proof_reference=inp.reference, proof_no=NumberingService.next_number(self.session, "REC", str(branch_id)), payment_type=inp.payment_type, idempotency_key=idempotency_key)
        self.session.add(payment); self.session.flush()
        self._audit(branch_id, actor_user_id, "REPAIR_PAYMENT_ADDED", repair, payment.payment_datetime, {"amount": str(payment.amount), "method": method})
        return payment

    def outstanding(self, repair_id: uuid.UUID, branch_id: uuid.UUID) -> Decimal:
        repair = self.session.scalar(select(Repair).where(Repair.id == repair_id, Repair.branch_id == branch_id))
        if repair is None: raise RepairValidationError("Repair not found")
        paid = self.session.scalar(select(func.coalesce(func.sum(RepairPayment.amount), 0)).where(RepairPayment.repair_id == repair_id, RepairPayment.payment_type == "RECEIPT")) or 0
        reversed_amount = self.session.scalar(select(func.coalesce(func.sum(RepairPayment.amount), 0)).where(RepairPayment.repair_id == repair_id, RepairPayment.payment_type == "REVERSAL")) or 0
        return self.money(Decimal(repair.total_amount) - Decimal(paid) + Decimal(reversed_amount))

    def finalize_amounts(self, repair_id: uuid.UUID, branch_id: uuid.UUID, actor_user_id: uuid.UUID, *, version: int | None = None, final_amount: Decimal, labour_amount: Decimal, repair_invoice_ref: str | None = None, description_amount: str | None = None, hand_over_date: date | None = None) -> Repair:
        if final_amount < ZERO or labour_amount < ZERO: raise RepairValidationError("Amounts cannot be negative")
        repair = self.session.scalar(select(Repair).where(Repair.id == repair_id, Repair.branch_id == branch_id).with_for_update())
        if repair is None: raise RepairValidationError("Repair not found")
        if version is not None and repair.version != version: raise RepairValidationError("Repair changed; reload before editing")
        repair.final_amount = self.money(final_amount); repair.total_amount = self.money(final_amount); repair.labour_amount = self.money(labour_amount)
        repair.repair_invoice_ref = repair_invoice_ref; repair.description_amount = description_amount; repair.hand_over_date = hand_over_date
        if repair.warranty_period and (hand_over_date or date.today()):
            start = hand_over_date or date.today()
            period = repair.warranty_period.strip()
            if period.upper() not in {"NONE", "NO WARRANTY", "CHECKING ONLY"}:
                import re
                m = re.fullmatch(r"(\d+)\s*(DAY|DAYS|MONTH|MONTHS|YEAR|YEARS)", period, re.I)
                if not m:
                    raise RepairValidationError("Unsupported repair warranty period")
                try:
                    expiry = calculate_expiry(start, m.group(2), int(m.group(1)))
                except WarrantyCalculationError as exc:
                    raise RepairValidationError(str(exc))
                existing = self.session.scalar(select(RepairWarranty).where(RepairWarranty.repair_id==repair.id).with_for_update())
                if existing is None:
                    self.session.add(RepairWarranty(repair_id=repair.id,start_date=start,expiry_date=expiry,warranty_period=period,status="ACTIVE"))
                else:
                    existing.start_date=start; existing.expiry_date=expiry; existing.warranty_period=period; existing.status="ACTIVE"
        repair.version += 1
        self._audit(branch_id, actor_user_id, "REPAIR_FINALIZED", repair, datetime.now(timezone.utc), {"final_amount": str(repair.final_amount), "labour_amount": str(repair.labour_amount)})
        self.session.flush(); return repair

    def deliver(self, repair_id: uuid.UUID, branch_id: uuid.UUID, actor_user_id: uuid.UUID, *, version: int | None = None, admin_override: bool = False) -> Repair:
        repair = self.session.scalar(select(Repair).where(Repair.id == repair_id, Repair.branch_id == branch_id).with_for_update())
        if repair is None:
            raise RepairValidationError("Repair not found")
        if version is not None and repair.version != version:
            raise RepairValidationError("Repair changed; reload before editing")
        if repair.status != "READY":
            raise RepairValidationError("Only READY repairs can be delivered")
        outstanding = self.outstanding(repair.id, branch_id)
        if outstanding > ZERO and not admin_override:
            raise RepairValidationError("Outstanding repair balance requires Admin approval before delivery")
        repair.status = "DELIVERED"
        repair.version += 1
        repair.hand_over_date = repair.hand_over_date or datetime.now(timezone.utc).date()
        if admin_override:
            repair.authorized_by = actor_user_id
        self._audit(branch_id, actor_user_id, "REPAIR_DELIVERED", repair, datetime.now(timezone.utc), {
            "outstanding": str(outstanding), "admin_override": admin_override,
        })
        self.session.flush()
        return repair

    def cancel(self, repair_id: uuid.UUID, branch_id: uuid.UUID, actor_user_id: uuid.UUID, *, version: int | None = None, reason: str) -> Repair:
        repair = self.session.scalar(select(Repair).where(Repair.id == repair_id, Repair.branch_id == branch_id).with_for_update())
        if repair is None: raise RepairValidationError("Repair not found")
        if version is not None and repair.version != version: raise RepairValidationError("Repair changed; reload before editing")
        if repair.status == "CANCELLED": raise RepairValidationError("Repair already cancelled")
        parts = list(self.session.scalars(select(RepairPart).where(RepairPart.repair_id == repair.id).with_for_update()))
        now = datetime.now(timezone.utc)
        for part in parts:
            if part.status == "USED":
                # Cancellation restores good/unused parts. A damaged part remains lost
                # and is explicitly recorded for Admin review; payment history is untouched.
                self._restore_part_if_good(part, branch_id, repair.id, now, actor_user_id)
        repair.status = "CANCELLED"; repair.version += 1; repair.notes = (repair.notes + "\n" if repair.notes else "") + f"Cancelled: {reason}"
        self._audit(branch_id, actor_user_id, "REPAIR_CANCELLED", repair, now, {"reason": reason})
        self.session.flush(); return repair

    def _restore_part_if_good(self, part: RepairPart, branch_id: uuid.UUID, repair_id: uuid.UUID, now: datetime, actor_user_id: uuid.UUID) -> None:
        movement = self.session.scalar(select(StockMovement).where(StockMovement.id == part.stock_movement_id).with_for_update()) if part.stock_movement_id else None
        if movement is None: return
        allocations = list(self.session.scalars(select(FifoAllocation).where(FifoAllocation.stock_movement_id == movement.id, FifoAllocation.purchase_lot_id.is_not(None)).order_by(FifoAllocation.created_at.desc(), FifoAllocation.id.desc()).with_for_update()))
        remaining = Decimal(part.quantity)
        reverse = StockMovement(branch_id=branch_id, item_id=part.item_id, source_type="REPAIR_PART_RETURN", source_id=repair_id, quantity_delta=part.quantity, occurred_at=now, reason="Repair cancellation")
        self.session.add(reverse); self.session.flush()
        for alloc in allocations:
            if remaining <= ZERO: break
            take = min(remaining, Decimal(alloc.allocated_quantity))
            lot = self.session.scalar(select(PurchaseLot).where(PurchaseLot.id == alloc.purchase_lot_id).with_for_update())
            if lot:
                lot.remaining_quantity = Decimal(lot.remaining_quantity) + take; lot.is_closed = False
                self.session.add(FifoAllocation(stock_movement_id=reverse.id, purchase_lot_id=lot.id, allocated_quantity=take, allocated_unit_cost=lot.unit_cost, allocation_status="REPAIR_RETURN", created_at=now))
                remaining -= take
        if remaining > ZERO:
            self.session.add(FifoAllocation(stock_movement_id=reverse.id, purchase_lot_id=None, allocated_quantity=remaining, allocated_unit_cost=None, allocation_status="UNRESOLVED_REPAIR_RETURN", created_at=now))
        part.status = "RETURNED"

    def _audit(self, branch_id, actor_user_id, action, repair, timestamp, after):
        self.session.add(AuditLog(branch_id=branch_id, actor_user_id=actor_user_id, action_type=action, entity_type="REPAIR", entity_id=repair.id, timestamp=timestamp, after_json=after, source_transaction_id=repair.id))
