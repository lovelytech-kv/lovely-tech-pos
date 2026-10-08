from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import DamageLossRecord, StockMovement, WarrantyHolding
from app.models.security import AuditLog, DocumentEvent
from app.models.warranty import ProductWarranty, WarrantyClaim
from app.services.numbering import NumberingService
from app.services.warranty_calculator import warranty_status
from app.fifo.engine import FifoEngine

ZERO = Decimal("0")

class WarrantyValidationError(ValueError):
    pass

@dataclass(frozen=True)
class WarrantyClaimRequest:
    branch_id: uuid.UUID
    created_by: uuid.UUID
    item_id: uuid.UUID
    product_warranty_id: uuid.UUID | None = None
    quantity: Decimal = Decimal("1")
    notes: str | None = None

class WarrantyService:
    def __init__(self, session: Session):
        self.session = session
        self.fifo = FifoEngine(session)

    def create_claim(self, req: WarrantyClaimRequest) -> WarrantyClaim:
        if req.quantity <= ZERO: raise WarrantyValidationError("Claim quantity must be greater than zero")
        now = datetime.now(timezone.utc)
        if req.product_warranty_id:
            warranty = self.session.scalar(select(ProductWarranty).where(ProductWarranty.id == req.product_warranty_id, ProductWarranty.branch_id == req.branch_id).with_for_update())
            if warranty is None: raise WarrantyValidationError("Warranty record not found")
            current = warranty_status(warranty.start_date, warranty.expiry_date, date.today())
            if current != 'ACTIVE':
                if current == 'EXPIRED': warranty.status = 'EXPIRED'
                raise WarrantyValidationError(f'Warranty is {current.lower().replace("_", " " )}')
        claim = WarrantyClaim(branch_id=req.branch_id, claim_no=NumberingService.next_number(self.session, "WCL", str(req.branch_id)), product_warranty_id=req.product_warranty_id, item_id=req.item_id, created_by=req.created_by, admin_decision="PENDING_ADMIN", holding_quantity=req.quantity, notes=req.notes)
        self.session.add(claim); self.session.flush()
        self.session.add(WarrantyHolding(branch_id=req.branch_id, item_id=req.item_id, warranty_claim_id=claim.id, quantity=req.quantity, status="HELD"))
        self.session.add(AuditLog(branch_id=req.branch_id, actor_user_id=req.created_by, action_type="WARRANTY_CLAIM_CREATED", entity_type="WARRANTY_CLAIM", entity_id=claim.id, timestamp=now, after_json={"claim_no": claim.claim_no, "quantity": str(req.quantity)}, source_transaction_id=claim.id))
        return claim

    def decide_supplier_claim(self, claim_id: uuid.UUID, branch_id: uuid.UUID, admin_user_id: uuid.UUID, *, version: int | None = None, supplier_process: str = "SUPPLIER_WARRANTY_CLAIM", notes: str | None = None) -> WarrantyClaim:
        claim = self._lock_claim(claim_id, branch_id)
        if version is not None and claim.version != version: raise WarrantyValidationError("Warranty claim changed; reload before editing")
        if claim.admin_decision != "PENDING_ADMIN": raise WarrantyValidationError("Warranty claim already decided")
        claim.admin_decision = "SUPPLIER_WARRANTY_CLAIM"; claim.version += 1; claim.supplier_process = supplier_process; claim.notes = notes or claim.notes
        self._set_holding(claim.id, "SUPPLIER_PENDING")
        self._audit(branch_id, admin_user_id, "WARRANTY_CLAIM_APPROVED_SUPPLIER", claim, {"decision": claim.admin_decision})
        return claim

    def decide_damage(self, claim_id: uuid.UUID, branch_id: uuid.UUID, admin_user_id: uuid.UUID, *, version: int | None = None, reason: str = "Warranty damage/loss") -> WarrantyClaim:
        claim = self._lock_claim(claim_id, branch_id)
        if version is not None and claim.version != version: raise WarrantyValidationError("Warranty claim changed; reload before editing")
        if claim.admin_decision != "PENDING_ADMIN": raise WarrantyValidationError("Warranty claim already decided")
        qty = Decimal(claim.holding_quantity or 0)
        claim.admin_decision = "DAMAGE_LOSS"; claim.version += 1; claim.supplier_process = None; claim.notes = reason
        self._set_holding(claim.id, "DAMAGE_LOSS")
        loss = DamageLossRecord(branch_id=branch_id, item_id=claim.item_id, quantity=qty, reason=reason, source_type="WARRANTY_CLAIM", source_id=claim.id, approved_by=admin_user_id)
        self.session.add(loss)
        self.session.flush()
        self._audit(branch_id, admin_user_id, "WARRANTY_CLAIM_DAMAGE_LOSS", claim, {"quantity": str(qty)})
        return claim


    def record_supplier_outcome(self, claim_id: uuid.UUID, branch_id: uuid.UUID, admin_user_id: uuid.UUID, *, version: int | None = None, outcome: str, quantity: Decimal | None = None, notes: str | None = None) -> WarrantyClaim:
        claim=self._lock_claim(claim_id,branch_id)
        if version is not None and claim.version != version: raise WarrantyValidationError("Warranty claim changed; reload before editing")
        if claim.admin_decision != "SUPPLIER_WARRANTY_CLAIM":
            raise WarrantyValidationError("Claim is not awaiting supplier outcome")
        if claim.replacement_outcome is not None:
            raise WarrantyValidationError("Supplier outcome has already been recorded")
        qty=Decimal(quantity if quantity is not None else claim.holding_quantity or 0)
        if outcome not in {"REPLACEMENT","SHOP_HELD_DAMAGE","CUSTOMER_KEEPS_ITEM"}:
            raise WarrantyValidationError("Invalid supplier outcome")
        if qty <= ZERO: raise WarrantyValidationError("Outcome quantity must be greater than zero")
        now=datetime.now(timezone.utc)
        if outcome == "REPLACEMENT":
            movement=StockMovement(branch_id=branch_id,item_id=claim.item_id,source_type="WARRANTY_REPLACEMENT",source_id=claim.id,quantity_delta=qty,occurred_at=now,reason=f"Warranty replacement {claim.claim_no}")
            self.session.add(movement); claim.replacement_outcome="WARRANTY_REPLACEMENT"; self._set_holding(claim.id,"REPLACED")
        elif outcome == "SHOP_HELD_DAMAGE":
            loss=DamageLossRecord(branch_id=branch_id,item_id=claim.item_id,quantity=qty,reason=notes or "Supplier rejected; shop-held item damaged/lost",source_type="WARRANTY_CLAIM",source_id=claim.id,approved_by=admin_user_id,review_status="APPROVED")
            self.session.add(loss)
            claim.replacement_outcome="SHOP_HELD_DAMAGE"; self._set_holding(claim.id,"DAMAGE_LOSS")
        else:
            claim.replacement_outcome="CUSTOMER_KEEPS_ITEM"; self._set_holding(claim.id,"CUSTOMER_KEEPS_ITEM")
        claim.notes=notes or claim.notes
        claim.version += 1
        self._audit(branch_id,admin_user_id,"WARRANTY_SUPPLIER_OUTCOME",claim,{"outcome":outcome,"quantity":str(qty)})
        self.session.flush(); return claim

    def record_supplier_replacement(self, claim_id: uuid.UUID, branch_id: uuid.UUID, admin_user_id: uuid.UUID, *, version: int | None = None, quantity: Decimal | None = None) -> WarrantyClaim:
        claim = self._lock_claim(claim_id, branch_id)
        if version is not None and claim.version != version: raise WarrantyValidationError("Warranty claim changed; reload before editing")
        if claim.admin_decision != "SUPPLIER_WARRANTY_CLAIM": raise WarrantyValidationError("Claim is not approved for supplier replacement")
        if claim.replacement_outcome is not None: raise WarrantyValidationError("Supplier replacement has already been recorded")
        qty = Decimal(quantity if quantity is not None else claim.holding_quantity or 0)
        if qty <= ZERO: raise WarrantyValidationError("Replacement quantity must be greater than zero")
        now = datetime.now(timezone.utc)
        movement = StockMovement(branch_id=branch_id, item_id=claim.item_id, source_type="WARRANTY_REPLACEMENT", source_id=claim.id, quantity_delta=qty, occurred_at=now, reason=f"Warranty claim {claim.claim_no} supplier replacement")
        self.session.add(movement)
        claim.replacement_outcome = "WARRANTY_REPLACEMENT"
        claim.version += 1
        self._set_holding(claim.id, "REPLACED")
        self._audit(branch_id, admin_user_id, "WARRANTY_REPLACEMENT_RECEIVED", claim, {"quantity": str(qty), "source_type": "WARRANTY_REPLACEMENT"})
        self.session.add(DocumentEvent(document_type="WARRANTY_CLAIM", document_id=claim.id, event_type="ORIGINAL", actor_user_id=admin_user_id, occurred_at=now, reason="Supplier replacement recorded"))
        self.session.flush(); return claim

    def _lock_claim(self, claim_id, branch_id):
        claim = self.session.scalar(select(WarrantyClaim).where(WarrantyClaim.id == claim_id, WarrantyClaim.branch_id == branch_id).with_for_update())
        if claim is None: raise WarrantyValidationError("Warranty claim not found")
        return claim

    def _set_holding(self, claim_id, status):
        rows = list(self.session.scalars(select(WarrantyHolding).where(WarrantyHolding.warranty_claim_id == claim_id).with_for_update()))
        for row in rows: row.status = status

    def _audit(self, branch_id, actor, action, claim, after):
        self.session.add(AuditLog(branch_id=branch_id, actor_user_id=actor, action_type=action, entity_type="WARRANTY_CLAIM", entity_id=claim.id, timestamp=datetime.now(timezone.utc), after_json=after, source_transaction_id=claim.id))
