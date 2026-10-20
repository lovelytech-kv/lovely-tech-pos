from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.fifo.engine import FifoEngine
from app.models.inventory import DamageLossRecord, FifoAllocation, PurchaseLot, StockMovement, SerializedUnit
from app.models.sales import Exchange, Return, ReturnLine, ReturnPayment, Sale, SaleLine
from app.models.security import AuditLog, DocumentEvent, IdempotencyKey
from app.services.numbering import NumberingService

CENT = Decimal("0.01")
QTY_ZERO = Decimal("0")


class ReturnValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ReturnLineInput:
    sale_line_id: uuid.UUID
    quantity: Decimal
    condition: str = "GOOD"  # GOOD / DAMAGED
    refund_amount: Decimal | None = None
    serialized_unit_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ReturnRequest:
    branch_id: uuid.UUID
    cashier_id: uuid.UUID
    original_sale_id: uuid.UUID
    lines: tuple[ReturnLineInput, ...]
    return_charge: Decimal = QTY_ZERO
    reason: str | None = None
    return_datetime: datetime | None = None
    admin_override: bool = False
    idempotency_key: str | None = None


@dataclass(frozen=True)
class ReturnResult:
    return_id: uuid.UUID
    return_no: str
    refund_total: Decimal
    return_charge: Decimal
    version: int = 1


@dataclass(frozen=True)
class ExchangeRequest:
    branch_id: uuid.UUID
    cashier_id: uuid.UUID
    return_id: uuid.UUID
    replacement_sale_id: uuid.UUID
    exchange_datetime: datetime | None = None
    version: int | None = None


@dataclass(frozen=True)
class ExchangeResult:
    exchange_id: uuid.UUID
    exchange_no: str
    difference_amount: Decimal


class ReturnService:
    ALLOWED_CONDITIONS = {"GOOD", "DAMAGED"}

    def __init__(self, session: Session):
        self.session = session
        self.fifo = FifoEngine(session)

    @staticmethod
    def money(value: Decimal) -> Decimal:
        return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)

    def _sale_and_line(self, sale_id: uuid.UUID, sale_line_id: uuid.UUID):
        sale = self.session.scalar(select(Sale).where(Sale.id == sale_id).with_for_update())
        if sale is None or sale.status != "COMPLETED":
            raise ReturnValidationError("Original sale is not available for return")
        line = self.session.scalar(select(SaleLine).where(SaleLine.id == sale_line_id).with_for_update())
        if line is None or line.sale_id != sale.id:
            raise ReturnValidationError("Sale line does not belong to the original sale")
        return sale, line

    def _already_returned(self, line_id: uuid.UUID) -> Decimal:
        value = self.session.scalar(
            select(func.coalesce(func.sum(ReturnLine.quantity), 0))
            .join(Return, Return.id == ReturnLine.return_id)
            .where(ReturnLine.original_sale_line_id == line_id, Return.status == "COMPLETED")
        )
        return Decimal(value or 0)

    def _restore_good_lineage(self, *, sale_line_id: uuid.UUID, return_movement: StockMovement, quantity: Decimal) -> Decimal:
        """Restore the exact FIFO lots allocated to this sale line."""
        sale_movement = self.session.scalar(
            select(StockMovement).where(
                StockMovement.source_type == "SALE",
                StockMovement.source_id == sale_line_id,
            ).order_by(StockMovement.occurred_at.desc(), StockMovement.id.desc())
        )
        if sale_movement is None:
            self.session.add(FifoAllocation(
                stock_movement_id=return_movement.id, purchase_lot_id=None,
                allocated_quantity=quantity, allocated_unit_cost=None,
                allocation_status="UNRESOLVED_RETURN", created_at=return_movement.occurred_at,
            ))
            return Decimal("0")
        allocations = list(self.session.scalars(
            select(FifoAllocation).where(
                FifoAllocation.stock_movement_id == sale_movement.id,
                FifoAllocation.purchase_lot_id.is_not(None),
            ).order_by(FifoAllocation.created_at.desc(), FifoAllocation.id.desc()).with_for_update()
        ))
        remaining = quantity
        restored_cost = Decimal("0")
        for alloc in allocations:
            if remaining <= QTY_ZERO:
                break
            take = min(remaining, Decimal(alloc.allocated_quantity))
            lot = self.session.scalar(select(PurchaseLot).where(PurchaseLot.id == alloc.purchase_lot_id).with_for_update())
            if lot is None:
                continue
            lot.remaining_quantity = Decimal(lot.remaining_quantity) + take
            lot.is_closed = False
            self.session.add(FifoAllocation(
                stock_movement_id=return_movement.id, purchase_lot_id=lot.id,
                allocated_quantity=take, allocated_unit_cost=lot.unit_cost,
                allocation_status="RETURN_RESTORED", created_at=return_movement.occurred_at,
            ))
            restored_cost += take * Decimal(lot.unit_cost)
            remaining -= take
        if remaining > QTY_ZERO:
            self.session.add(FifoAllocation(
                stock_movement_id=return_movement.id, purchase_lot_id=None,
                allocated_quantity=remaining, allocated_unit_cost=None,
                allocation_status="UNRESOLVED_RETURN", created_at=return_movement.occurred_at,
            ))
        return restored_cost

    def record_refund_payment(self, *, return_id: uuid.UUID, branch_id: uuid.UUID, actor_user_id: uuid.UUID, payment_method: str, amount: Decimal, payment_datetime: datetime | None = None, reference: str | None = None, idempotency_key: str | None = None) -> ReturnPayment:
        if idempotency_key:
            existing = self.session.scalar(select(ReturnPayment).where(ReturnPayment.idempotency_key == idempotency_key).with_for_update())
            if existing is not None:
                if existing.return_id != return_id or existing.payment_method != payment_method or self.money(existing.amount) != self.money(amount) or existing.reference != reference:
                    raise ReturnValidationError("Idempotency key was already used for a different refund payment")
                return existing
        ret = self.session.scalar(select(Return).where(Return.id == return_id, Return.branch_id == branch_id).with_for_update())
        if ret is None or ret.status != "COMPLETED":
            raise ReturnValidationError("Completed return not found")
        if payment_method not in {"CASH", "CARD", "ONLINE"}:
            raise ReturnValidationError("Invalid refund payment method")
        amount = self.money(amount)
        paid = self.session.scalar(select(func.coalesce(func.sum(ReturnPayment.amount), 0)).where(ReturnPayment.return_id == ret.id)) or 0
        remaining = self.money(Decimal(ret.refund_total) - Decimal(paid))
        if amount > remaining:
            raise ReturnValidationError("Refund payment exceeds remaining refund amount")
        row = ReturnPayment(return_id=ret.id, payment_method=payment_method, amount=amount, payment_datetime=payment_datetime or datetime.now(timezone.utc), reference=reference, idempotency_key=idempotency_key)
        self.session.add(row)
        self.session.flush()
        paid_after = self.money(Decimal(paid) + amount)
        self.session.add(AuditLog(branch_id=branch_id, actor_user_id=actor_user_id, action_type="RETURN_REFUND_PAID", entity_type="RETURN", entity_id=ret.id, timestamp=row.payment_datetime, after_json={"payment_method":payment_method,"amount":str(amount),"paid_total":str(paid_after),"refund_total":str(ret.refund_total)}, source_transaction_id=row.id))
        return row

    def refund_paid_total(self, return_id: uuid.UUID) -> Decimal:
        return self.money(Decimal(self.session.scalar(select(func.coalesce(func.sum(ReturnPayment.amount), 0)).where(ReturnPayment.return_id == return_id)) or 0))

    @staticmethod
    def canonical_request_hash(request: ReturnRequest) -> str:
        payload = {
            "branch_id": str(request.branch_id),
            "cashier_id": str(request.cashier_id),
            "original_sale_id": str(request.original_sale_id),
            "return_charge": str(request.return_charge),
            "reason": request.reason,
            "return_datetime": request.return_datetime.isoformat() if request.return_datetime else None,
            "admin_override": request.admin_override,
            "lines": [
                {
                    "sale_line_id": str(x.sale_line_id),
                    "quantity": str(x.quantity),
                    "condition": x.condition,
                    "refund_amount": str(x.refund_amount) if x.refund_amount is not None else None,
                    "serialized_unit_id": str(x.serialized_unit_id) if x.serialized_unit_id else None,
                }
                for x in request.lines
            ],
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()

    def _get_idempotent_replay(self, request: ReturnRequest, request_hash: str) -> ReturnResult | None:
        if not request.idempotency_key:
            return None
        key = self.session.scalar(
            select(IdempotencyKey).where(IdempotencyKey.key == request.idempotency_key).with_for_update()
        )
        if key is None:
            return None
        if key.request_hash != request_hash:
            raise ReturnValidationError("Idempotency key was already used for a different request")
        if not key.completed_at or not key.response_json:
            raise ReturnValidationError("The same request is currently being completed; retry after transaction finishes")
        response = key.response_json
        return ReturnResult(
            return_id=uuid.UUID(response["return_id"]),
            return_no=response["return_no"],
            refund_total=Decimal(response["refund_total"]),
            return_charge=Decimal(response["return_charge"]),
            version=int(response.get("version", 1)),
        )

    def _reserve_idempotency(self, request: ReturnRequest, request_hash: str, result: ReturnResult) -> None:
        if not request.idempotency_key:
            return
        response = {
            "return_id": str(result.return_id),
            "return_no": result.return_no,
            "refund_total": str(result.refund_total),
            "return_charge": str(result.return_charge),
            "version": result.version,
        }
        row = IdempotencyKey(
            key=request.idempotency_key,
            user_id=request.cashier_id,
            request_hash=request_hash,
            created_at=datetime.now(timezone.utc),
            response_json=response,
            completed_at=datetime.now(timezone.utc),
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
                raise ReturnValidationError("Idempotency key conflict")
            raise ReturnValidationError("Idempotency request has already completed")

    def complete(self, request: ReturnRequest, *, version: int | None = None) -> ReturnResult:
        request_hash = self.canonical_request_hash(request)
        replay = self._get_idempotent_replay(request, request_hash)
        if replay is not None:
            return replay
        if not request.lines:
            raise ReturnValidationError("Return must contain at least one line")
        if request.return_charge < QTY_ZERO:
            raise ReturnValidationError("Return charge cannot be negative")
        now = request.return_datetime or datetime.now(timezone.utc)
        sale = self.session.scalar(select(Sale).where(Sale.id == request.original_sale_id).with_for_update())
        if sale is None or sale.branch_id != request.branch_id or sale.status != "COMPLETED":
            raise ReturnValidationError("Original sale is not available for return")
        if not request.admin_override and (now.date() - sale.sale_datetime.date()).days > 7:
            raise ReturnValidationError("Return is outside the normal 7-day window")

        return_no = NumberingService.next_number(self.session, "RET", str(request.branch_id))
        ret = Return(
            branch_id=request.branch_id,
            return_no=return_no,
            original_sale_id=sale.id,
            cashier_id=request.cashier_id,
            return_datetime=now,
            refund_total=QTY_ZERO,
            return_charge=self.money(request.return_charge),
            status="DRAFT",
            reason=request.reason,
        )
        self.session.add(ret)
        self.session.flush()
        if version is not None and ret.version != version:
            raise ReturnValidationError("Return changed; reload before editing")

        gross_refund = QTY_ZERO
        for inp in request.lines:
            if inp.quantity <= QTY_ZERO:
                raise ReturnValidationError("Return quantity must be greater than zero")
            if inp.condition not in self.ALLOWED_CONDITIONS:
                raise ReturnValidationError("Invalid return condition")
            _, line = self._sale_and_line(sale.id, inp.sale_line_id)
            already = self._already_returned(line.id)
            if already + inp.quantity > Decimal(line.quantity):
                raise ReturnValidationError("Return quantity exceeds the sold quantity")
            if inp.serialized_unit_id and line.serialized_unit_id != inp.serialized_unit_id:
                raise ReturnValidationError("Serialized unit does not match original sale line")
            auto_refund = self.money((Decimal(line.final_total) / Decimal(line.quantity)) * inp.quantity)
            refund = self.money(inp.refund_amount if inp.refund_amount is not None else auto_refund)
            if refund < QTY_ZERO:
                raise ReturnValidationError("Refund amount cannot be negative")
            gross_refund += refund
            self.session.add(ReturnLine(
                return_id=ret.id,
                original_sale_line_id=line.id,
                item_id=line.item_id,
                quantity=inp.quantity,
                refund_amount=refund,
                condition=inp.condition,
            ))
            movement = StockMovement(
                branch_id=request.branch_id,
                item_id=line.item_id,
                source_type="RETURN" if inp.condition == "GOOD" else "DAMAGE_RETURN",
                source_id=ret.id,
                quantity_delta=inp.quantity if inp.condition == "GOOD" else Decimal("-0.000"),
                occurred_at=now,
                reason=f"Return {return_no}",
            )
            self.session.add(movement)
            self.session.flush()
            if inp.condition == "GOOD":
                self._restore_good_lineage(sale_line_id=line.id, return_movement=movement, quantity=inp.quantity)
            else:
                self.session.delete(movement)
                self.session.flush()
                self.session.add(DamageLossRecord(
                    branch_id=request.branch_id,
                    item_id=line.item_id,
                    quantity=inp.quantity,
                    reason=f"Damaged return {return_no}",
                    source_type="RETURN",
                    source_id=ret.id,
                    approved_by=request.cashier_id,
                    review_status="APPROVED",
                ))
            if line.serialized_unit_id:
                unit = self.session.scalar(select(SerializedUnit).where(SerializedUnit.id == line.serialized_unit_id).with_for_update())
                if unit:
                    unit.status = "IN_STOCK" if inp.condition == "GOOD" else "DAMAGED"

        refund_total = self.money(gross_refund - self.money(request.return_charge))
        ret.refund_total = refund_total
        ret.status = "COMPLETED"
        ret.version += 1
        self.session.add(AuditLog(
            branch_id=request.branch_id,
            actor_user_id=request.cashier_id,
            action_type="RETURN_COMPLETED",
            entity_type="RETURN",
            entity_id=ret.id,
            timestamp=now,
            after_json={"return_no": return_no, "refund_total": str(refund_total), "return_charge": str(request.return_charge)},
            source_transaction_id=ret.id,
        ))
        self.session.add(DocumentEvent(
            document_type="RETURN",
            document_id=ret.id,
            event_type="ORIGINAL",
            actor_user_id=request.cashier_id,
            occurred_at=now,
            reason="Return completed",
        ))
        self.session.flush()
        result = ReturnResult(ret.id, return_no, refund_total, self.money(request.return_charge), ret.version)
        self._reserve_idempotency(request, request_hash, result)
        return result


class ExchangeService:
    def __init__(self, session: Session):
        self.session = session

    def complete(self, request: ExchangeRequest) -> ExchangeResult:
        now = request.exchange_datetime or datetime.now(timezone.utc)
        ret = self.session.scalar(select(Return).where(Return.id == request.return_id, Return.branch_id == request.branch_id).with_for_update())
        sale = self.session.scalar(select(Sale).where(Sale.id == request.replacement_sale_id, Sale.branch_id == request.branch_id).with_for_update())
        if ret is None or ret.status != "COMPLETED":
            raise ReturnValidationError("Return is not completed")
        if sale is None or sale.status != "COMPLETED":
            raise ReturnValidationError("Replacement sale is not completed")
        if sale.id == ret.original_sale_id:
            raise ReturnValidationError("Replacement sale must be different from the original sale")
        if ret.branch_id != request.branch_id or sale.branch_id != request.branch_id:
            raise ReturnValidationError("Return and replacement sale must belong to the same branch")
        existing = self.session.scalar(select(Exchange).where(Exchange.return_id == ret.id))
        if existing is not None:
            raise ReturnValidationError("Return is already linked to an exchange")
        if request.version is not None and ret.version != request.version:
            raise ReturnValidationError("Return changed; reload before editing")
        difference = Decimal(sale.grand_total) - Decimal(ret.refund_total)
        exchange_no = NumberingService.next_number(self.session, "EXC", str(request.branch_id))
        ex = Exchange(
            branch_id=request.branch_id,
            exchange_no=exchange_no,
            return_id=ret.id,
            replacement_sale_id=sale.id,
            difference_amount=difference.quantize(CENT, rounding=ROUND_HALF_UP),
            status="COMPLETED",
        )
        self.session.add(ex)
        self.session.flush()  # assign ex.id before it is referenced by the audit/document rows
        ret.version += 1
        self.session.add(AuditLog(
            branch_id=request.branch_id,
            actor_user_id=request.cashier_id,
            action_type="EXCHANGE_COMPLETED",
            entity_type="EXCHANGE",
            entity_id=ex.id,
            timestamp=now,
            after_json={"exchange_no": exchange_no, "difference_amount": str(ex.difference_amount), "return_version": ret.version},
            source_transaction_id=ex.id,
        ))
        self.session.add(DocumentEvent(
            document_type="EXCHANGE",
            document_id=ex.id,
            event_type="ORIGINAL",
            actor_user_id=request.cashier_id,
            occurred_at=now,
            reason="Exchange completed",
        ))
        self.session.flush()
        return ExchangeResult(ex.id, exchange_no, ex.difference_amount)

