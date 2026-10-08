from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.services.sales import SaleService, SaleRequest, SaleLineInput, PaymentInput, SaleValidationError
from app.services.warranty_calculator import calculate_expiry
from app.schemas.api import PurchaseQuantityCorrectionIn, ManualWarrantyRegistrationIn, UserDiscountLimitIn


def test_cashier_discount_limit_rejects_over_limit():
    req = SaleRequest(
        branch_id=uuid4(), cashier_id=uuid4(),
        lines=(SaleLineInput(item_id=uuid4(), quantity=Decimal('1'), unit_price=Decimal('1000'), discount=Decimal('150')) ,),
        payments=(PaymentInput(method='CASH', amount=Decimal('850')) ,),
        discount_limit_percent=Decimal('10'),
    )
    with pytest.raises(SaleValidationError, match='Discount limit exceeded'):
        SaleService.validate_request(req)


def test_admin_discount_approval_bypasses_cashier_limit():
    req = SaleRequest(
        branch_id=uuid4(), cashier_id=uuid4(),
        lines=(SaleLineInput(item_id=uuid4(), quantity=Decimal('1'), unit_price=Decimal('1000'), discount=Decimal('150')) ,),
        payments=(PaymentInput(method='CASH', amount=Decimal('850')) ,),
        discount_limit_percent=Decimal('10'), admin_discount_approved=True,
    )
    SaleService.validate_request(req)


def test_custom_warranty_rule_is_calculated():
    assert calculate_expiry(date(2026, 1, 31), 'CUSTOM', custom_rule='1 MONTH') == date(2026, 2, 28)


def test_locked_completion_schemas_expose_required_controls():
    assert PurchaseQuantityCorrectionIn(purchase_line_id=uuid4(), quantity=Decimal('2'), reason='Correction').quantity == Decimal('2')
    assert ManualWarrantyRegistrationIn(reference_no='MW-1', start_date=date(2026,1,1)).reference_no == 'MW-1'
    assert UserDiscountLimitIn(discount_limit_percent=Decimal('15')).discount_limit_percent == Decimal('15')

def test_target_percentage_is_not_clamped_to_100():
    from app.services.targets import TargetProgress
    p=TargetProgress(uuid4(),'SALES_AMOUNT',Decimal('100'),Decimal('250'),Decimal('250'))
    assert p.percentage == Decimal('250')
