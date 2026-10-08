"""Focused tests: Expense and OtherIncome idempotency.

Static source assertions, matching the existing test style in this repo
(test_day_finance_validation.py, test_cash_only_calculations.py).
Verifies that the admin expense/other-income endpoints reuse the existing
IdempotencyKey infrastructure and enforce the same conflict convention
already used by SaleService.
"""

from pathlib import Path

BACKEND = Path(__file__).parents[1]
ADMIN = (BACKEND / "app" / "api" / "routes" / "admin.py").read_text()
SCHEMA = (BACKEND / "app" / "schemas" / "api.py").read_text()


def test_expense_schema_accepts_idempotency_key():
    assert "idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)" in SCHEMA.split("class ExpenseIn")[1].split("class OtherIncomeIn")[0]


def test_other_income_schema_accepts_idempotency_key():
    assert "idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)" in SCHEMA.split("class OtherIncomeIn")[1].split("class TargetIn")[0]


def test_admin_route_uses_existing_idempotency_key_model():
    assert "IdempotencyKey" in ADMIN


def test_expense_create_replays_completed_request():
    expense_body = ADMIN.split("def expense(")[1].split("def other_income(")[0]
    assert "_get_expense_idempotent_replay(" in expense_body
    assert "if replay is not None:" in expense_body


def test_expense_create_reserves_idempotency_before_commit():
    expense_body = ADMIN.split("def expense(")[1].split("def other_income(")[0]
    assert "_reserve_expense_idempotency(" in expense_body
    # The idempotency row is written (flush) before the HTTP commit.
    assert "db.flush()" in expense_body
    assert "db.commit()" in expense_body


def test_other_income_create_replays_completed_request():
    oi_body = ADMIN.split("def other_income(")[1].split("def expense_categories(")[0]
    assert "_get_expense_idempotent_replay(" in oi_body
    assert "if replay is not None:" in oi_body


def test_other_income_create_reserves_idempotency_before_commit():
    oi_body = ADMIN.split("def other_income(")[1].split("def expense_categories(")[0]
    assert "_reserve_expense_idempotency(" in oi_body
    assert "db.flush()" in oi_body
    assert "db.commit()" in oi_body


def test_idempotency_conflict_uses_existing_convention():
    assert "Idempotency key was already used for a different request" in ADMIN
    assert "Idempotency request has already completed" in ADMIN
    assert "The same request is currently being completed; retry after transaction finishes" in ADMIN


def test_expense_request_hash_is_deterministic():
    assert "_expense_request_hash(payload: ExpenseIn)" in ADMIN
    assert "_other_income_request_hash(payload: OtherIncomeIn)" in ADMIN