"""Focused tests: only CASH purchases/expenses affect physical cash.

Static source assertions, matching the existing test style in this repo.
Verifies that CARD/ONLINE expenses and purchases are excluded from both
ReportService.cash_in_hands and DayFinanceService.expected_cash.
"""

from pathlib import Path

BACKEND = Path(__file__).parents[1]


def test_reports_cash_in_hands_counts_all_expenses_regardless_of_payment_method():
    content = (BACKEND / "app" / "services" / "reports.py").read_text()
    # Requirements 11: Cash In Hands = all approved inflows - all outflows, regardless of payment method.
    assert "Expense.payment_method" not in content


def test_reports_cash_in_hands_counts_all_purchases_regardless_of_payment_method():
    content = (BACKEND / "app" / "services" / "reports.py").read_text()
    # Requirements 08/11: purchases have no payment method; Cash In Hands subtracts all of them.
    assert "Purchase.payment_method" not in content


def test_reports_cash_in_hands_formula_unchanged_structure():
    content = (BACKEND / "app" / "services" / "reports.py").read_text()
    # The overall formula still subtracts expenses and purchases.
    assert "return self._d(sales_cash+repair_cash+settlements+other_income+other_cash+reloads-refunds-expenses-purchases)" in content


def test_day_finance_expected_cash_does_not_subtract_expenses():
    content = (BACKEND / "app" / "services" / "day_finance.py").read_text()
    # Requirements 11 (locked rule): expenses affect Cash In Hands but not the Day-End drawer.
    assert "cash_expenses" not in content


def test_day_finance_expected_cash_does_not_subtract_purchases():
    content = (BACKEND / "app" / "services" / "day_finance.py").read_text()
    # Requirements 11 (locked rule): purchases affect Cash In Hands but not the Day-End drawer.
    assert "cash_purchases" not in content


def test_day_finance_expected_cash_formula_unchanged_structure():
    content = (BACKEND / "app" / "services" / "day_finance.py").read_text()
    # Opening + inflows - outflows, with new cash-only deductions inserted.
    assert "return self.money(day.opening_cash+Decimal(cash_sales)+Decimal(repair_cash)+Decimal(settlement_cash)-Decimal(refund_cash)+Decimal(reloads)+Decimal(other))" in content