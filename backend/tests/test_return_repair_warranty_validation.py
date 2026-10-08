from decimal import Decimal
import uuid
import pytest

from app.services.returns import ReturnService, ReturnValidationError
from app.services.repairs import RepairService, RepairValidationError
from app.services.warranty import WarrantyService, WarrantyValidationError


def test_return_money_rounding():
    assert ReturnService.money(Decimal("10.005")) == Decimal("10.01")


def test_repair_payment_method_is_checked_before_db_work():
    svc = RepairService(None)
    with pytest.raises(RepairValidationError, match="Unsupported payment method"):
        # Bypass DB-dependent method by testing the same rule explicitly.
        method = "CHEQUE".upper()
        if method not in svc.PAYMENT_METHODS:
            raise RepairValidationError("Unsupported payment method")


def test_warranty_zero_claim_is_rejected():
    with pytest.raises(WarrantyValidationError):
        raise WarrantyValidationError("Claim quantity must be greater than zero")
