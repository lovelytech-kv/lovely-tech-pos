from decimal import Decimal
from app.schemas.api import SaleIn, PaymentIn
from app.api.deps import token_hash

def test_token_hash_is_stable_and_non_reversible_shape():
    assert token_hash("abc") == token_hash("abc")
    assert len(token_hash("abc")) == 64

def test_sale_schema_accepts_split_payment_payload():
    payload = SaleIn(
        lines=[{"item_id":"00000000-0000-0000-0000-000000000001","quantity":"1","unit_price":"1500","discount":"0"}],
        payments=[PaymentIn(method="CASH", amount=Decimal("500")), PaymentIn(method="CARD", amount=Decimal("1000"))]
    )
    assert len(payload.payments) == 2
