"""Admin sale void (Requirements 06/16): the invoice number stays on the VOIDED record and is never reused.

A void is only allowed while it is still a clean correction: sale COMPLETED, no return / settlement /
warranty claim against it and its business day not closed (after Day End use Return/Exchange so the
refund is a cash movement on the day it happens). Stock goes back to the exact FIFO lots, IMEI units
become IN_STOCK again, warranties are voided, and the sale drops out of sales/profit/drawer reports.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.finance import DaySession
from app.models.inventory import SerializedUnit, StockMovement
from app.models.sales import CreditSettlement, Payment, Return, ReturnLine, Sale, SaleLine
from app.models.security import AuditLog
from app.models.warranty import ProductWarranty, WarrantyClaim
from app.services.returns import ReturnService


class SaleVoidError(ValueError):
    pass


class SaleVoidService:
    def __init__(self, session: Session):
        self.session = session

    def void(self, *, sale: Sale, reason: str, actor_user_id, version: int | None) -> Sale:
        if not (reason or "").strip():
            raise SaleVoidError("Void reason is required")
        if version is None or sale.version != version:
            raise SaleVoidError("Sale changed or version missing; reload before voiding")
        if sale.status != "COMPLETED":
            raise SaleVoidError(f"Only a completed sale can be voided (this one is {sale.status})")
        lines = list(self.session.scalars(select(SaleLine).where(SaleLine.sale_id == sale.id).with_for_update()))
        line_ids = [x.id for x in lines]
        if self.session.scalar(select(func.count(ReturnLine.id)).join(Return, Return.id == ReturnLine.return_id)
                               .where(ReturnLine.original_sale_line_id.in_(line_ids))):
            raise SaleVoidError("This sale already has a return; it cannot be voided")
        if self.session.scalar(select(func.count(CreditSettlement.id)).where(CreditSettlement.sale_id == sale.id)):
            raise SaleVoidError("This sale has credit settlements; it cannot be voided")
        warranties = list(self.session.scalars(select(ProductWarranty).where(ProductWarranty.sale_line_id.in_(line_ids)).with_for_update()))
        if warranties and self.session.scalar(select(func.count(WarrantyClaim.id)).where(WarrantyClaim.product_warranty_id.in_([w.id for w in warranties]))):
            raise SaleVoidError("A warranty claim exists for this sale; it cannot be voided")
        closed = self.session.scalar(select(DaySession.id).where(
            DaySession.branch_id == sale.branch_id, func.date(sale.sale_datetime) == DaySession.business_date, DaySession.status == "CLOSED"))
        if closed is not None:
            raise SaleVoidError("The business day of this sale is closed; use a Return/Exchange instead")

        now = datetime.now(timezone.utc)
        returns = ReturnService(self.session)
        for line in lines:
            movement = StockMovement(branch_id=sale.branch_id, item_id=line.item_id, source_type="SALE_VOID", source_id=line.id,
                                     quantity_delta=line.quantity, occurred_at=now, reason=f"Void {sale.invoice_no}")
            self.session.add(movement)
            self.session.flush()
            returns._restore_good_lineage(sale_line_id=line.id, return_movement=movement, quantity=line.quantity)
            if line.serialized_unit_id:
                unit = self.session.scalar(select(SerializedUnit).where(SerializedUnit.id == line.serialized_unit_id).with_for_update())
                if unit:
                    unit.status = "IN_STOCK"
        for w in warranties:
            w.status = "VOIDED"
            w.version += 1
        before = {"status": sale.status, "grand_total": str(sale.grand_total)}
        sale.status = "VOIDED"
        sale.void_reason = reason.strip()
        sale.version += 1
        self.session.add(AuditLog(branch_id=sale.branch_id, actor_user_id=actor_user_id, action_type="SALE_VOIDED", entity_type="SALE",
                                  entity_id=sale.id, timestamp=now, reason=reason.strip(), before_json=before,
                                  after_json={"status": "VOIDED", "invoice_no": sale.invoice_no}, source_transaction_id=sale.id))
        self.session.flush()
        return sale
