from decimal import Decimal
import uuid
import pytest

from app.services.sales import (
    PaymentInput,
    SaleLineInput,
    SaleRequest,
    SaleService,
    SaleValidationError,
)


def make_request(**overrides):
    data = dict(
        branch_id=uuid.uuid4(),
        cashier_id=uuid.uuid4(),
        lines=(SaleLineInput(item_id=uuid.uuid4(), quantity=Decimal("2"), unit_price=Decimal("150.00"), discount=Decimal("10.00")),),
        payments=(PaymentInput(method="cash", amount=Decimal("290.00")),),
    )
    data.update(overrides)
    return SaleRequest(**data)


def test_sale_request_validation_accepts_split_payment_methods():
    request = make_request(
        payments=(
            PaymentInput(method="CASH", amount=Decimal("100.00")),
            PaymentInput(method="CARD", amount=Decimal("190.00")),
        )
    )
    SaleService.validate_request(request)


def test_manual_sale_requires_manual_reference():
    request = make_request(document_type="MANUAL")
    with pytest.raises(SaleValidationError, match="Manual invoice reference"):
        SaleService.validate_request(request)


def test_canonical_request_hash_is_deterministic():
    request = make_request()
    assert SaleService.canonical_request_hash(request) == SaleService.canonical_request_hash(request)


def test_canonical_hash_changes_when_price_changes():
    first = make_request()
    second = make_request(lines=(SaleLineInput(item_id=first.lines[0].item_id, quantity=Decimal("2"), unit_price=Decimal("151.00"), discount=Decimal("10.00")),))
    assert SaleService.canonical_request_hash(first) != SaleService.canonical_request_hash(second)


def test_invalid_payment_method_is_rejected():
    request = make_request(payments=(PaymentInput(method="CHEQUE", amount=Decimal("290.00")),))
    with pytest.raises(SaleValidationError, match="Unsupported payment method"):
        SaleService.validate_request(request)


def test_sale_payment_methods_are_case_insensitive():
    request = make_request(payments=(PaymentInput(method="online", amount=Decimal("290.00")),))
    SaleService.validate_request(request)


def test_sale_time_warranty_override_requires_duration_for_calendar_type():
    request = make_request(lines=(SaleLineInput(item_id=uuid.uuid4(), quantity=Decimal("1"), unit_price=Decimal("100"), warranty_type="DAYS"),))
    with pytest.raises(SaleValidationError, match="duration is required"):
        SaleService.validate_request(request)


def test_sale_time_warranty_override_accepts_custom_rule():
    request = make_request(lines=(SaleLineInput(item_id=uuid.uuid4(), quantity=Decimal("1"), unit_price=Decimal("100"), warranty_type="CUSTOM", warranty_custom_rule="45 DAYS"),))
    SaleService.validate_request(request)


def test_sale_time_warranty_override_rejects_custom_rule_without_type():
    request = make_request(lines=(SaleLineInput(item_id=uuid.uuid4(), quantity=Decimal("1"), unit_price=Decimal("100"), warranty_type="NONE", warranty_custom_rule="45 DAYS"),))
    with pytest.raises(SaleValidationError, match="cannot have duration/custom rule"):
        SaleService.validate_request(request)
