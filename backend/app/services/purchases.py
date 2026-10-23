from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import uuid, hashlib, json

from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.fifo.engine import FifoEngine
from app.models.inventory import Purchase, PurchaseLine, SerializedUnit, StockMovement
from app.models.master import Item, ItemType
from app.models.security import AuditLog, IdempotencyKey
from app.services.numbering import NumberingService


class PurchaseService:
    """Atomic purchase entry and private-cost completion workflow."""

    def __init__(self, session: Session):
        self.session = session
        self.fifo = FifoEngine(session)

    def create_purchase(
        self, *, branch_id: uuid.UUID, actor_user_id: uuid.UUID, purchase_date: date,
        payment_method: str = "CASH",
        lines: list[dict], reference_no: str | None = None, notes: str | None = None,
        supplier_id: uuid.UUID | None = None, admin_side: bool = False, idempotency_key: str | None = None,
    ) -> Purchase:
        if not lines:
            raise ValueError("At least one purchase line is required")
        payment_method = (payment_method or "CASH").upper()
        if payment_method not in {"CASH", "CARD", "ONLINE"}:
            raise ValueError("Unsupported purchase payment method")
        request_payload = {
            "branch_id": str(branch_id), "actor_user_id": str(actor_user_id), "purchase_date": purchase_date.isoformat(),
            "payment_method": payment_method,
            "reference_no": reference_no.strip() if reference_no else None, "notes": notes,
            "supplier_id": str(supplier_id) if supplier_id else None, "admin_side": admin_side,
            "lines": [{k: (str(v) if isinstance(v, (Decimal, uuid.UUID, date)) else v) for k, v in sorted(x.items())} for x in lines],
        }
        request_hash = hashlib.sha256(json.dumps(request_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if idempotency_key:
            existing = self.session.scalar(select(IdempotencyKey).where(IdempotencyKey.key == idempotency_key).with_for_update())
            if existing:
                if existing.request_hash != request_hash:
                    raise ValueError("Idempotency key was already used for a different purchase")
                if existing.response_json and existing.response_json.get("purchase_id"):
                    existing_purchase = self.session.get(Purchase, uuid.UUID(existing.response_json["purchase_id"]))
                    if existing_purchase is not None:
                        return existing_purchase
                raise ValueError("The same purchase request is currently being completed; retry after transaction finishes")
            row = IdempotencyKey(key=idempotency_key, user_id=actor_user_id, request_hash=request_hash, created_at=datetime.now(timezone.utc))
            try:
                with self.session.begin_nested():
                    self.session.add(row); self.session.flush()
            except IntegrityError:
                existing = self.session.scalar(select(IdempotencyKey).where(IdempotencyKey.key == idempotency_key).with_for_update())
                if existing is None or existing.request_hash != request_hash:
                    raise ValueError("Idempotency key conflict")
                if existing.response_json and existing.response_json.get("purchase_id"):
                    existing_purchase = self.session.get(Purchase, uuid.UUID(existing.response_json["purchase_id"]))
                    if existing_purchase is not None:
                        return existing_purchase
                raise ValueError("The same purchase request is currently being completed; retry after transaction finishes")
        if supplier_id is not None:
            supplier = self.session.scalar(select(__import__('app.models.master', fromlist=['Supplier']).Supplier).where(
                __import__('app.models.master', fromlist=['Supplier']).Supplier.id == supplier_id,
                __import__('app.models.master', fromlist=['Supplier']).Supplier.is_active.is_(True),
            ))
            if supplier is None:
                raise ValueError("Active supplier not found")
            if not admin_side:
                raise ValueError("Supplier assignment is Admin-only")
        purchase = Purchase(
            branch_id=branch_id,
            reference_no=reference_no.strip() if reference_no else None,
            supplier_id=supplier_id if admin_side else None,
            purchase_date=purchase_date,
            payment_method=payment_method,
            status="PENDING_COST",
            notes=notes,
        )
        self.session.add(purchase)
        self.session.flush()
        seen_serials: set[str] = set()
        for raw in lines:
            item_id = raw["item_id"]
            quantity = Decimal(raw["quantity"])
            if quantity <= 0:
                raise ValueError("Purchase quantity must be greater than zero")
            item = self.session.scalar(select(Item).where(Item.id == item_id, Item.is_active.is_(True)).with_for_update())
            if not item:
                raise ValueError("Active item not found")
            serials = self._validate_serials(branch_id, item, quantity, raw.get("serial_numbers"), seen_serials)
            line_date = raw.get("line_date") or purchase_date
            line = PurchaseLine(
                purchase_id=purchase.id, item_id=item.id, quantity=quantity,
                unit_cost=None, line_date=line_date, notes=raw.get("notes"),
            )
            self.session.add(line)
            self.session.flush()
            for serial in serials:
                self.session.add(SerializedUnit(branch_id=branch_id, item_id=item.id, serial_number=serial, status="IN_STOCK"))
            # Requirements: stock increases immediately even when cost is unknown.
            # The positive movement has no FIFO lot until Admin completes the cost.
            self.session.add(StockMovement(
                branch_id=branch_id, item_id=item.id, source_type="PURCHASE_PENDING",
                source_id=purchase.id, quantity_delta=quantity,
                occurred_at=datetime.combine(line_date, datetime.min.time(), tzinfo=timezone.utc),
                reason="Purchase entered before cost completion",
            ))
        self.session.add(AuditLog(
            branch_id=branch_id, actor_user_id=actor_user_id, action_type="PURCHASE_CREATED",
            entity_type="PURCHASE", entity_id=purchase.id, timestamp=datetime.now(timezone.utc),
            after_json={"payment_method": payment_method, "status": purchase.status, "line_count": len(lines)},
            source_transaction_id=purchase.id,
        ))
        self.session.flush()
        if idempotency_key:
            idem = self.session.scalar(select(IdempotencyKey).where(IdempotencyKey.key == idempotency_key).with_for_update())
            if idem is not None:
                idem.response_json = {"purchase_id": str(purchase.id), "reference_no": purchase.reference_no}
                idem.completed_at = datetime.now(timezone.utc)
        return purchase

    def _validate_serials(self, branch_id, item: Item, quantity: Decimal, raw_serials, seen: set[str]) -> list[str]:
        """Serialized items (phones) need one unique IMEI/serial per unit; others must not carry any."""
        item_type = self.session.get(ItemType, item.item_type_id)
        serialized = bool(item_type and item_type.is_serialized)
        cleaned = [str(x).strip().upper() for x in (raw_serials or []) if str(x).strip()]
        if not serialized:
            if raw_serials:
                raise ValueError(f"{item.item_code} is not a serialized item; remove the IMEI/serial numbers")
            return []
        if quantity != quantity.to_integral_value():
            raise ValueError(f"Serialized item {item.item_code} must be purchased in whole units")
        if len(cleaned) != int(quantity):
            raise ValueError(f"{item.item_code} needs exactly {int(quantity)} IMEI/serial number(s); {len(cleaned)} entered")
        for serial in cleaned:
            if len(serial) > 100:
                raise ValueError("IMEI/serial number is too long")
            if serial in seen:
                raise ValueError(f"IMEI/serial {serial} is entered more than once")
            seen.add(serial)
        taken = self.session.scalars(select(SerializedUnit.serial_number).where(
            SerializedUnit.branch_id == branch_id, SerializedUnit.serial_number.in_(cleaned))).all()
        if taken:
            raise ValueError(f"IMEI/serial already exists in the system: {', '.join(sorted(taken))}")
        return cleaned

    def complete_line_cost(self, *, purchase: Purchase, line: PurchaseLine, unit_cost: Decimal, actor_user_id: uuid.UUID | None = None) -> None:
        if purchase.status not in {"PENDING_COST", "COMPLETED"}:
            raise ValueError(f"Purchase cannot receive cost in status {purchase.status}")
        if line.quantity <= 0:
            raise ValueError("Purchase quantity must be greater than zero")
        if unit_cost < 0:
            raise ValueError("Purchase cost cannot be negative")
        if line.unit_cost is not None:
            if line.unit_cost == unit_cost:
                raise ValueError("Purchase cost is already completed for this line")
            raise ValueError("Changing an existing purchase cost requires controlled correction/recalculation")

        line.unit_cost = unit_cost
        lot = self.fifo.create_purchase_lot(
            branch_id=purchase.branch_id, purchase_line_id=line.id, item_id=line.item_id,
            quantity=line.quantity, unit_cost=unit_cost, lot_date=line.line_date,
            movement_source_id=purchase.id, create_stock_movement=False,
        )
        remaining = self.session.scalar(select(func.count(PurchaseLine.id)).where(
            PurchaseLine.purchase_id == purchase.id, PurchaseLine.unit_cost.is_(None)))
        purchase.status = "COMPLETED" if not remaining else "PENDING_COST"
        self.session.add(AuditLog(
            branch_id=purchase.branch_id, actor_user_id=actor_user_id,
            action_type="PURCHASE_COST_COMPLETED", entity_type="PURCHASE_LINE", entity_id=line.id,
            timestamp=datetime.now(timezone.utc), after_json={"unit_cost": str(unit_cost), "lot_id": str(lot.id)},
            source_transaction_id=purchase.id,
        ))
        self.session.flush()
