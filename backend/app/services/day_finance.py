from __future__ import annotations
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.finance import DayEnd, DaySession, OtherCashIn, ReloadEntry
from app.models.sales import Payment, RepairPayment, CreditSettlement, Repair, ReturnPayment, Return

CENT=Decimal('0.01')
ZERO=Decimal('0')
class DayFinanceError(ValueError): pass
@dataclass(frozen=True)
class DayStartResult:
    day_session_id: uuid.UUID
    business_date: date
    opening_cash: Decimal
@dataclass(frozen=True)
class DayEndResult:
    day_session_id: uuid.UUID
    expected_cash: Decimal
    actual_cash: Decimal
    difference: Decimal

class DayFinanceService:
    CASH_METHOD='CASH'
    DENOMINATIONS = (5000, 2000, 1000, 500, 100, 50, 20)

    def __init__(self, session: Session): self.session=session

    @classmethod
    def validate_denominations(cls, denominations: dict | None, expected: Decimal, *, field_name: str) -> dict[str, int]:
        values = denominations or {}
        normalized: dict[str, int] = {}
        for key, value in values.items():
            try:
                denom = int(key)
            except (TypeError, ValueError) as exc:
                raise DayFinanceError(f"Invalid denomination: {key}") from exc
            if denom not in cls.DENOMINATIONS:
                raise DayFinanceError(f"Unsupported denomination: {denom}")
            if isinstance(value, bool) or int(value) != value or value < 0:
                raise DayFinanceError(f"{field_name} denomination counts must be non-negative integers")
            normalized[str(denom)] = int(value)
        total = sum(Decimal(k) * Decimal(v) for k, v in normalized.items())
        if cls.money(total) != cls.money(expected):
            raise DayFinanceError(f"{field_name} denominations total must equal Rs. {cls.money(expected):.2f}")
        return normalized
    @staticmethod
    def money(v: Decimal)->Decimal: return Decimal(v).quantize(CENT, rounding=ROUND_HALF_UP)
    def _open(self, branch_id, business_date):
        row = self.session.scalar(select(DaySession).where(DaySession.branch_id==branch_id,DaySession.business_date==business_date,DaySession.status.in_(['OPEN','SHIFT_ENDED'])).with_for_update())
        # Lazy auto-close: the API is the authoritative clock boundary, so a
        # cashier shift cannot remain reopenable indefinitely when nobody is
        # actively running a scheduler on the LAN server.
        if row and row.status == 'SHIFT_ENDED' and row.shift_end_at and row.shift_end_at + timedelta(hours=1) <= datetime.now(timezone.utc):
            row.status = 'CLOSED'
            self.session.flush()
            return None
        return row
    def start_day(self, *, branch_id, user_id, business_date: date, opening_cash: Decimal, denominations=None, note=None):
        if opening_cash<ZERO: raise DayFinanceError('Opening cash cannot be negative')
        if self._open(branch_id,business_date): raise DayFinanceError('Business day is already open')
        normalized_denoms = self.validate_denominations(denominations, opening_cash, field_name='Opening cash')
        row=DaySession(branch_id=branch_id,business_date=business_date,started_at=datetime.now(timezone.utc),started_by=user_id,status='OPEN',opening_cash=self.money(opening_cash),opening_note=note,opening_denominations=normalized_denoms)
        self.session.add(row); self.session.flush(); return DayStartResult(row.id,row.business_date,row.opening_cash)
    def continue_day(self, *, branch_id, business_date: date):
        row=self._open(branch_id,business_date)
        if not row: raise DayFinanceError('No open business day')
        if row.status=='SHIFT_ENDED': row.status='OPEN'; row.shift_end_at=None; row.shift_end_by=None
        return row
    def shift_end(self, *, branch_id,business_date,user_id):
        row=self._open(branch_id,business_date)
        if not row: raise DayFinanceError('No open business day')
        row.status='SHIFT_ENDED'; row.shift_end_at=datetime.now(timezone.utc); row.shift_end_by=user_id; self.session.flush(); return row


    def correct_opening(self, *, day_session_id, user_id, version: int | None = None, opening_cash: Decimal, denominations: dict, reason: str):
        day=self.session.scalar(select(DaySession).where(DaySession.id==day_session_id).with_for_update())
        if not day or day.status not in {'OPEN','SHIFT_ENDED'}: raise DayFinanceError('Day is not open')
        if version is not None and day.version != version: raise DayFinanceError('Day session changed; reload before editing')
        if not reason.strip(): raise DayFinanceError('Correction reason is required')
        normalized=self.validate_denominations(denominations,opening_cash,field_name='Opening cash')
        old={'opening_cash':str(day.opening_cash),'opening_denominations':day.opening_denominations}
        day.opening_cash=self.money(opening_cash); day.opening_denominations=normalized; day.version += 1
        from app.models.security import AuditLog
        self.session.add(AuditLog(branch_id=day.branch_id,actor_user_id=user_id,action_type='DAY_OPENING_CORRECTED',entity_type='DAY_SESSION',entity_id=day.id,timestamp=datetime.now(timezone.utc),reason=reason,before_json=old,after_json={'opening_cash':str(day.opening_cash),'opening_denominations':normalized},source_transaction_id=day.id))
        self.session.flush(); return day

    def reopen_closed_day(self, *, branch_id, business_date: date, user_id):
        row=self.session.scalar(select(DaySession).where(DaySession.branch_id==branch_id,DaySession.business_date==business_date,DaySession.status=='CLOSED').order_by(DaySession.created_at.desc()).with_for_update())
        if not row: raise DayFinanceError('Closed business day not found')
        row.status='OPEN'; row.shift_end_at=None; row.shift_end_by=None
        self.session.add(__import__('app.models.security',fromlist=['AuditLog']).AuditLog(branch_id=branch_id,actor_user_id=user_id,action_type='DAY_REOPENED',entity_type='DAY_SESSION',entity_id=row.id,timestamp=datetime.now(timezone.utc),reason='Admin reopened closed business day',source_transaction_id=row.id))
        self.session.flush(); return row

    def add_reload(self, *, day_session_id, user_id, provider, amount, note=None):
        if amount<=ZERO: raise DayFinanceError('Reload amount must be positive')
        if provider not in {'Dialog', 'Airtel', 'Mobitel', 'Hutch'}:
            raise DayFinanceError('Unsupported reload provider')
        day=self.session.scalar(select(DaySession).where(DaySession.id==day_session_id).with_for_update())
        if not day or day.status not in {'OPEN','SHIFT_ENDED'}: raise DayFinanceError('Day is not open')
        existing=self.session.scalar(select(ReloadEntry).where(ReloadEntry.day_session_id==day.id).with_for_update())
        if existing is not None:
            raise DayFinanceError('Reload has already been entered for this business day')
        row=ReloadEntry(day_session_id=day.id,provider=provider,amount=self.money(amount),entered_by=user_id,note=note)
        self.session.add(row); self.session.flush(); return row
    def add_other_cash_in(self, *, branch_id,day_session_id,user_id,amount,note=None):
        if amount<=ZERO: raise DayFinanceError('Cash-in amount must be positive')
        row=OtherCashIn(branch_id=branch_id,day_session_id=day_session_id,transaction_datetime=datetime.now(timezone.utc),amount=self.money(amount),entered_by=user_id,note=note); self.session.add(row); self.session.flush(); return row
    def expected_cash(self, day: DaySession)->Decimal:
        from app.models.sales import Sale
        cash_sales=self.session.scalar(select(func.coalesce(func.sum(Payment.amount),0)).join(Sale,Sale.id==Payment.sale_id).where(Sale.branch_id==day.branch_id,func.date(Sale.sale_datetime)==day.business_date,Payment.payment_method=='CASH')) or 0
        repair_cash=self.session.scalar(select(func.coalesce(func.sum(RepairPayment.amount),0)).join(Repair, Repair.id==RepairPayment.repair_id).where(Repair.branch_id==day.branch_id,func.date(RepairPayment.payment_datetime)==day.business_date,RepairPayment.payment_method=='CASH',RepairPayment.payment_type=='RECEIPT')) or 0
        settlement_cash=self.session.scalar(select(func.coalesce(func.sum(CreditSettlement.amount),0)).where(CreditSettlement.branch_id==day.branch_id,func.date(CreditSettlement.settlement_datetime)==day.business_date,CreditSettlement.payment_method=='CASH')) or 0
        refund_cash=self.session.scalar(select(func.coalesce(func.sum(ReturnPayment.amount),0)).join(Return, Return.id==ReturnPayment.return_id).where(Return.branch_id==day.branch_id,func.date(ReturnPayment.payment_datetime)==day.business_date,ReturnPayment.payment_method=='CASH',Return.status=='COMPLETED')) or 0
        reloads=self.session.scalar(select(func.coalesce(func.sum(ReloadEntry.amount),0)).where(ReloadEntry.day_session_id==day.id)) or 0
        other=self.session.scalar(select(func.coalesce(func.sum(OtherCashIn.amount),0)).where(OtherCashIn.day_session_id==day.id)) or 0
        from app.models.sales import Expense
        from app.models.inventory import Purchase, PurchaseLine
        cash_expenses=self.session.scalar(select(func.coalesce(func.sum(Expense.amount),0)).where(Expense.branch_id==day.branch_id,Expense.expense_date==day.business_date,Expense.status=='APPROVED',Expense.payment_method=='CASH')) or 0
        cash_purchases=self.session.scalar(select(func.coalesce(func.sum(PurchaseLine.quantity*PurchaseLine.unit_cost),0)).join(Purchase,Purchase.id==PurchaseLine.purchase_id).where(Purchase.branch_id==day.branch_id,Purchase.purchase_date==day.business_date,PurchaseLine.unit_cost.is_not(None),Purchase.payment_method=='CASH')) or 0
        return self.money(day.opening_cash+Decimal(cash_sales)+Decimal(repair_cash)+Decimal(settlement_cash)-Decimal(refund_cash)+Decimal(reloads)+Decimal(other)-Decimal(cash_expenses)-Decimal(cash_purchases))
    def end_day(self, *, day_session_id,user_id,version: int | None = None,actual_cash,denominations=None,reason,note=None)->DayEndResult:
        day=self.session.scalar(select(DaySession).where(DaySession.id==day_session_id).with_for_update())
        if not day or day.status not in {'OPEN','SHIFT_ENDED'}: raise DayFinanceError('Day is not open')
        if version is not None and day.version != version: raise DayFinanceError('Day session changed; reload before editing')
        if actual_cash<ZERO: raise DayFinanceError('Actual cash cannot be negative')
        expected=self.expected_cash(day); actual=self.money(actual_cash); diff=self.money(actual-expected)
        normalized_denoms = self.validate_denominations(denominations, actual, field_name='Actual cash')
        if not str(reason or '').strip():
            raise DayFinanceError('Day End reason is required')
        row=DayEnd(day_session_id=day.id,expected_cash=expected,actual_cash=actual,difference=diff,actual_denominations=normalized_denoms,reload_total=self.money(self.session.scalar(select(func.coalesce(func.sum(ReloadEntry.amount),0)).where(ReloadEntry.day_session_id==day.id)) or 0),reason=reason,note=note,completed_by=user_id,completed_at=datetime.now(timezone.utc))
        self.session.add(row)
        from app.services.targets import TargetService
        TargetService(self.session).snapshot_completed_periods(branch_id=day.branch_id, as_of=day.business_date, captured_by=user_id)
        day.status='CLOSED'; day.version += 1; self.session.flush(); return DayEndResult(day.id,expected,actual,diff)

