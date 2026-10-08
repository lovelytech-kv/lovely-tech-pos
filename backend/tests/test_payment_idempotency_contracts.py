def test_financial_payment_models_have_idempotency_keys():
    from app.models.sales import RepairPayment, ReturnPayment, CreditSettlement
    assert RepairPayment.__table__.c.idempotency_key.unique is True
    assert ReturnPayment.__table__.c.idempotency_key.unique is True
    assert CreditSettlement.__table__.c.idempotency_key.unique is True


def test_payment_input_schemas_accept_idempotency_key():
    from app.schemas.api import RepairPaymentIn, ReturnPaymentIn, SettlementIn
    key = "test-idempotency-123"
    assert RepairPaymentIn(idempotency_key=key, method="CASH", amount="10").idempotency_key == key
    assert ReturnPaymentIn(idempotency_key=key, payment_method="CASH", amount="10").idempotency_key == key
    from uuid import uuid4
    assert SettlementIn(idempotency_key=key, customer_id=uuid4(), amount="10", payment_method="CASH").idempotency_key == key


def test_warranty_supplier_outcome_has_duplicate_execution_guard():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[2] / "backend/app/services/warranty.py").read_text()
    assert "Supplier outcome has already been recorded" in source
    assert "Supplier replacement has already been recorded" in source
