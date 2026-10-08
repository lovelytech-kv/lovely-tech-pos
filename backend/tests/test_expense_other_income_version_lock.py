"""Focused tests: Expense and OtherIncome optimistic-locking.

Static source assertions, matching the existing test style in this repo
(test_day_finance_validation.py, test_cash_only_calculations.py).
Verifies that the admin decision endpoints enforce version locking.
"""

from pathlib import Path

BACKEND = Path(__file__).parents[1]
ADMIN = (BACKEND / "app" / "api" / "routes" / "admin.py").read_text()
SCHEMA = (BACKEND / "app" / "schemas" / "api.py").read_text()


def test_expense_decision_requires_version():
    assert "if version is None: raise HTTPException(409,'Expense version is required; reload the record')" in ADMIN


def test_expense_decision_rejects_stale_version():
    assert "if row.version != version: raise HTTPException(409,'Expense changed; reload before editing')" in ADMIN


def test_expense_decision_increments_version():
    assert "row.version += 1" in ADMIN.split("def expense_decision")[1].split("def audit")[0]


def test_expense_decision_returns_version():
    assert "'version':row.version}" in ADMIN.split("def expense_decision")[1].split("def audit")[0]


def test_expense_pending_list_exposes_version():
    assert "'version':x.version}" in ADMIN.split("def pending_expenses")[1].split("def expense_decision")[0]


def test_other_income_decision_requires_version():
    assert "if version is None: raise HTTPException(409,'Other income version is required; reload the record')" in ADMIN


def test_other_income_decision_rejects_stale_version():
    assert "if row.version != version: raise HTTPException(409,'Other income changed; reload before editing')" in ADMIN


def test_other_income_decision_increments_version():
    assert "row.version += 1" in ADMIN.split("def other_income_decision")[1]


def test_other_income_decision_returns_version():
    assert "'version':row.version}" in ADMIN.split("def other_income_decision")[1]


def test_expense_and_other_income_models_carry_version_mixin():
    sales = (BACKEND / "app" / "models" / "sales.py").read_text()
    assert "class Expense(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):" in sales
    assert "class OtherIncome(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):" in sales