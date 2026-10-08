from __future__ import annotations
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.sales import Customer, Sale
from app.models.sales import CreditSettlement
from app.services.numbering import NumberingService
class SettlementError(ValueError): pass
class SettlementService:
    METHODS={'CASH','CARD','ONLINE'}
    def __init__(self,session:Session): self.session=session
    def settle(self, *, branch_id, customer_id, user_id, amount, payment_method, sale_id=None, reference=None, proof_reference=None, idempotency_key=None):
        if amount<=0: raise SettlementError('Settlement amount must be positive')
        if idempotency_key:
            existing = self.session.scalar(select(CreditSettlement).where(CreditSettlement.idempotency_key == idempotency_key).with_for_update())
            if existing is not None:
                if existing.customer_id != customer_id or existing.payment_method != payment_method.upper() or Decimal(existing.amount) != Decimal(amount) or existing.sale_id != sale_id or existing.reference != reference:
                    raise SettlementError("Idempotency key was already used for a different settlement")
                return existing
        method=payment_method.upper()
        if method not in self.METHODS: raise SettlementError('Unsupported payment method')
        customer=self.session.scalar(select(Customer).where(Customer.id==customer_id,Customer.is_active.is_(True)).with_for_update())
        if not customer: raise SettlementError('Customer not found')
        # Credit is represented by unpaid sale total; settled amounts reduce it.
        from app.models.sales import Payment
        gross=self.session.scalar(select(func.coalesce(func.sum(Sale.grand_total),0)).where(Sale.branch_id==branch_id,Sale.customer_id==customer_id,Sale.status=='COMPLETED')) or 0
        paid=self.session.scalar(select(func.coalesce(func.sum(Payment.amount),0)).join(Sale,Sale.id==Payment.sale_id).where(Sale.branch_id==branch_id,Sale.customer_id==customer_id)) or 0
        settled=self.session.scalar(select(func.coalesce(func.sum(CreditSettlement.amount),0)).where(CreditSettlement.branch_id==branch_id,CreditSettlement.customer_id==customer_id)) or 0
        outstanding=Decimal(gross)-Decimal(paid)-Decimal(settled)
        if amount>outstanding: raise SettlementError('Settlement exceeds customer outstanding')
        row=CreditSettlement(branch_id=branch_id,customer_id=customer_id,sale_id=sale_id,payment_method=method,amount=amount,settlement_datetime=datetime.now(timezone.utc),previous_outstanding=outstanding,remaining_outstanding=outstanding-amount,reference=reference,proof_reference=proof_reference,proof_no=NumberingService.next_number(self.session,"REC",str(branch_id)),idempotency_key=idempotency_key)
        self.session.add(row); self.session.flush(); return row
