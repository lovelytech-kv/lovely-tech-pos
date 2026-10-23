from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.sales import Sale, SaleLine, Payment, Return, ReturnLine, Repair, RepairPayment, CreditSettlement, Expense, OtherIncome, ReturnPayment
from app.models.finance import OtherCashIn, ReloadEntry, DaySession
from app.models.sales import Expense, OtherIncome
from app.models.inventory import StockMovement, FifoAllocation

@dataclass(frozen=True)
class SalesSummary:
    sales_total: Decimal
    cash_total: Decimal
    card_total: Decimal
    online_total: Decimal
    sales_count: int
    cost_total: Decimal
    gross_profit: Decimal
    expenses_total: Decimal
    other_income_total: Decimal
    net_profit: Decimal
    refunds_total: Decimal = Decimal("0")
    return_charge_total: Decimal = Decimal("0")
    returned_cost_total: Decimal = Decimal("0")
    repair_income: Decimal = Decimal("0")
    repair_profit: Decimal = Decimal("0")
    damage_loss_total: Decimal = Decimal("0")

@dataclass(frozen=True)
class CashierSummary:
    cashier_id: object
    cashier_name: str
    sales_count: int
    sales_total: Decimal
    cost_total: Decimal
    gross_profit: Decimal

class ReportService:
    def __init__(self,session:Session): self.session=session

    @staticmethod
    def _d(v) -> Decimal: return Decimal(v or 0)

    def _return_metrics(self, *, branch_id, start: date, end: date):
        rows=self.session.execute(
            select(Return.id, Return.refund_total, Return.return_charge)
            .where(Return.branch_id==branch_id, func.date(Return.return_datetime).between(start,end), Return.status=='COMPLETED')
        ).all()
        refunds=sum((self._d(r.refund_total) for r in rows), Decimal('0'))
        charges=sum((self._d(r.return_charge) for r in rows), Decimal('0'))
        returned_cost=Decimal('0')
        for r in rows:
            movements=self.session.scalars(select(StockMovement).where(
                StockMovement.branch_id==branch_id,
                StockMovement.source_id==r.id,
                StockMovement.source_type.in_(['RETURN','DAMAGE_RETURN'])
            )).all()
            for m in movements:
                allocs=self.session.scalars(select(FifoAllocation).where(FifoAllocation.stock_movement_id==m.id)).all()
                for a in allocs:
                    if a.allocated_unit_cost is not None and m.source_type=='RETURN':
                        returned_cost += self._d(a.allocated_quantity) * self._d(a.allocated_unit_cost)
        return self._d(refunds), self._d(charges), self._d(returned_cost)

    def _repair_metrics(self, *, branch_id, start: date, end: date):
        from app.models.sales import Repair, RepairPart
        rows=self.session.scalars(select(Repair).where(Repair.branch_id==branch_id,func.date(Repair.date_in).between(start,end),Repair.status.in_(['DELIVERED','RETURNED TO CUSTOMER']))).all()
        income=sum((self._d(r.final_amount) for r in rows),Decimal('0'))
        costs=Decimal('0')
        for r in rows:
            costs += self._d(self.session.scalar(select(func.coalesce(func.sum(RepairPart.fifo_cost),0)).where(RepairPart.repair_id==r.id)))
        return self._d(income), self._d(income-costs)

    def _damage_loss_cost(self, *, branch_id, start: date, end: date):
        rows=self.session.scalars(select(StockMovement).where(StockMovement.branch_id==branch_id,StockMovement.source_type.in_(['DAMAGE_LOSS','STOCK_ADJUSTMENT']),StockMovement.quantity_delta<0,func.date(StockMovement.occurred_at).between(start,end))).all()
        total=Decimal('0')
        for m in rows:
            total += sum((self._d(a.allocated_quantity)*self._d(a.allocated_unit_cost) for a in self.session.scalars(select(FifoAllocation).where(FifoAllocation.stock_movement_id==m.id)).all() if a.allocated_unit_cost is not None),Decimal('0'))
        return self._d(total)

    def sales_summary(self, *, branch_id, start:date, end:date)->SalesSummary:
        if end<start: raise ValueError('End date cannot be before start date')
        q=select(func.coalesce(func.sum(Sale.grand_total),0),func.count(Sale.id),func.coalesce(func.sum(Sale.total_cost),0)).where(
            Sale.branch_id==branch_id,func.date(Sale.sale_datetime).between(start,end),Sale.status=='COMPLETED')
        sales_total,count,cost=self.session.execute(q).one(); sales_total=self._d(sales_total); cost=self._d(cost)
        def pay(method):
            return self._d(self.session.scalar(select(func.coalesce(func.sum(Payment.amount),0)).join(Sale,Sale.id==Payment.sale_id).where(
                Sale.branch_id==branch_id,func.date(Sale.sale_datetime).between(start,end),Sale.status=='COMPLETED',Payment.payment_method==method)))
        cash,card,online=pay('CASH'),pay('CARD'),pay('ONLINE')
        expenses=self._d(self.session.scalar(select(func.coalesce(func.sum(Expense.amount),0)).where(Expense.branch_id==branch_id,Expense.expense_date.between(start,end),Expense.status=='APPROVED')))
        income=self._d(self.session.scalar(select(func.coalesce(func.sum(OtherIncome.amount),0)).where(OtherIncome.branch_id==branch_id,OtherIncome.income_date.between(start,end),OtherIncome.status=='APPROVED')))
        refunds,charges,returned_cost=self._return_metrics(branch_id=branch_id,start=start,end=end)
        repair_income,repair_profit=self._repair_metrics(branch_id=branch_id,start=start,end=end)
        damage_loss=self._damage_loss_cost(branch_id=branch_id,start=start,end=end)
        gross=sales_total-refunds-(cost-returned_cost)+charges+repair_profit-damage_loss
        net=gross-expenses+income
        return SalesSummary(sales_total,cash,card,online,int(count or 0),cost,gross,expenses,income,net,refunds,charges,returned_cost,repair_income,repair_profit,damage_loss)


    def cash_in_hands(self, *, branch_id, start: date, end: date) -> Decimal:
        from app.models.sales import Repair, RepairPayment, CreditSettlement, Return, ReturnPayment, Expense, OtherIncome
        from app.models.inventory import Purchase, PurchaseLine
        sales_cash=self._d(self.session.scalar(select(func.coalesce(func.sum(Payment.amount),0)).join(Sale,Sale.id==Payment.sale_id).where(Sale.branch_id==branch_id,func.date(Payment.payment_datetime).between(start,end),Sale.status=='COMPLETED')))
        repair_cash=self._d(self.session.scalar(select(func.coalesce(func.sum(RepairPayment.amount),0)).join(Repair,Repair.id==RepairPayment.repair_id).where(Repair.branch_id==branch_id,func.date(RepairPayment.payment_datetime).between(start,end),RepairPayment.payment_type=='RECEIPT')))
        settlements=self._d(self.session.scalar(select(func.coalesce(func.sum(CreditSettlement.amount),0)).where(CreditSettlement.branch_id==branch_id,func.date(CreditSettlement.settlement_datetime).between(start,end))))
        other_income=self._d(self.session.scalar(select(func.coalesce(func.sum(OtherIncome.amount),0)).where(OtherIncome.branch_id==branch_id,OtherIncome.income_date.between(start,end),OtherIncome.status=='APPROVED')))
        other_cash=self._d(self.session.scalar(select(func.coalesce(func.sum(OtherCashIn.amount),0)).where(OtherCashIn.branch_id==branch_id,func.date(OtherCashIn.transaction_datetime).between(start,end))))
        reloads=self._d(self.session.scalar(select(func.coalesce(func.sum(ReloadEntry.amount),0)).join(DaySession,DaySession.id==ReloadEntry.day_session_id).where(DaySession.branch_id==branch_id,func.date(ReloadEntry.created_at).between(start,end))))
        refunds=self._d(self.session.scalar(select(func.coalesce(func.sum(ReturnPayment.amount),0)).join(Return,Return.id==ReturnPayment.return_id).where(Return.branch_id==branch_id,func.date(ReturnPayment.payment_datetime).between(start,end),Return.status=='COMPLETED')))
        expenses=self._d(self.session.scalar(select(func.coalesce(func.sum(Expense.amount),0)).where(Expense.branch_id==branch_id,Expense.expense_date.between(start,end),Expense.status=='APPROVED')))
        purchases=self._d(self.session.scalar(select(func.coalesce(func.sum(PurchaseLine.quantity*PurchaseLine.unit_cost),0)).join(Purchase,Purchase.id==PurchaseLine.purchase_id).where(Purchase.branch_id==branch_id,Purchase.purchase_date.between(start,end),PurchaseLine.unit_cost.is_not(None))))
        return self._d(sales_cash+repair_cash+settlements+other_income+other_cash+reloads-refunds-expenses-purchases)

    def cashier_summary(self, *, branch_id, start: date, end: date):
        rows=self.session.execute(select(Sale.cashier_id, func.count(Sale.id), func.coalesce(func.sum(Sale.grand_total),0), func.coalesce(func.sum(Sale.total_cost),0))
            .where(Sale.branch_id==branch_id,func.date(Sale.sale_datetime).between(start,end),Sale.status=='COMPLETED')
            .group_by(Sale.cashier_id)).all()
        from app.models.master import User
        out=[]
        for cashier_id,count,total,cost in rows:
            u=self.session.get(User,cashier_id)
            total=self._d(total); cost=self._d(cost)
            out.append(CashierSummary(cashier_id,u.display_name if u else str(cashier_id),int(count),total,cost,total-cost))
        return out
