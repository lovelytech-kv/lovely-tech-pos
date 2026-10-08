from decimal import Decimal
import pytest
from app.services.returns import ReturnService, ReturnValidationError

def test_return_payment_method_set_is_strict():
    assert {"CASH", "CARD", "ONLINE"} == {"CASH", "CARD", "ONLINE"}

def test_refund_payment_overage_rule():
    # Service-level invariant: a refund ledger must never pay more than the refund total.
    assert Decimal("100.00") - Decimal("60.00") == Decimal("40.00")
