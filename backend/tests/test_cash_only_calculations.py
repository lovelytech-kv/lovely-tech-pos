"""Focused tests: only CASH purchases/expenses affect physical cash.

Static source assertions, matching the existing test style in this repo.
Verifies that CARD/ONLINE expenses and purchases are excluded from both
ReportService.cash_in_hands and DayFinanceService.expected_cash.
"""

from pathlib import Path

BACKEND = Path(__file__).parents[1]


def test_reports_cash_in_hands_filters_cash_expenses():
    content = (BACKEND / "app" / "services" / "reports.py").read_text()
    # Expenses in cash-in-hands must be restricted to CASH only.
    assert "Expense.payment_method=='CASH'" in content
    assert "expenses=self._d(self.session.scalar(select(func.coalesce(func.sum(Expense.amount),0)).where(Expense.branch_id==branch_id,Expense.expense_date.between(start,end),Expense.status=='APPROVED',Expense.payment_method=='CASH')))" in content


def test_reports_cash_in_hands_filters_cash_purchases():
    content = (BACKEND / "app" / "services" / "reports.py").read_text()
    # Purchases in cash-in-hands must be restricted to CASH only.
    assert "Purchase.payment_method=='CASH'" in content
    assert "purchases=self._d(self.session.scalar(select(func.coalesce(func.sum(PurchaseLine.quantity*PurchaseLine.unit_cost),0)).join(Purchase,Purchase.id==PurchaseLine.purchase_id).where(Purchase.branch_id==branch_id,Purchase.purchase_date.between(start,end),PurchaseLine.unit_cost.is_not(None),Purchase.payment_method=='CASH')))" in content


def test_reports_cash_in_hands_formula_unchanged_structure():
    content = (BACKEND / "app" / "services" / "reports.py").read_text()
    # The overall formula still subtracts expenses and purchases.
    assert "return self._d(sales_cash+repair_cash+settlements+other_income+other_cash+reloads-refunds-expenses-purchases)" in content


def test_day_finance_expected_cash_subtracts_cash_expenses():
    content = (BACKEND / "app" / "services" / "day_finance.py").read_text()
    assert "cash_expenses=self.session.scalar(select(func.coalesce(func.sum(Expense.amount),0)).where(Expense.branch_id==day.branch_id,Expense.expense_date==day.business_date,Expense.status=='APPROVED',Expense.payment_method=='CASH')) or 0" in content
    assert "-Decimal(cash_expenses)" in content


def test_day_finance_expected_cash_subtracts_cash_purchases():
    content = (BACKEND / "app" / "services" / "day_finance.py").read_text()
    assert "cash_purchases=self.session.scalar(select(func.coalesce(func.sum(PurchaseLine.quantity*PurchaseLine.unit_cost),0)).join(Purchase,Purchase.id==PurchaseLine.purchase_id).where(Purchase.branch_id==day.branch_id,Purchase.purchase_date==day.business_date,PurchaseLine.unit_cost.is_not(None),Purchase.payment_method=='CASH')) or 0" in content
    assert "-Decimal(cash_purchases)" in content


def test_day_finance_expected_cash_formula_unchanged_structure():
    content = (BACKEND / "app" / "services" / "day_finance.py").read_text()
    # Opening + inflows - outflows, with new cash-only deductions inserted.
    assert "return self.money(day.opening_cash+Decimal(cash_sales)+Decimal(repair_cash)+Decimal(settlement_cash)-Decimal(refund_cash)+Decimal(reloads)+Decimal(other)-Decimal(cash_expenses)-Decimal(cash_purchases))" in content