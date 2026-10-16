import uuid
from decimal import Decimal
import pytest

from app.services.items import (
    ItemCreationInput,
    ItemCreationResult,
    ItemCreationError,
    ItemService,
    create_item_from_schema,
)
from app.schemas.items import ItemCreateIn


def test_item_creation_input_dataclass():
    """ItemCreationInput dataclass should accept all fields."""
    input_data = ItemCreationInput(
        item_code="ITEM-000001",
        description="Test Item",
        category_id=uuid.uuid4(),
        item_type_id=uuid.uuid4(),
        brand="TestBrand",
        model="TestModel",
        master_sale_price=Decimal("100.00"),
        barcode="1234567890123",
    )
    assert input_data.item_code == "ITEM-000001"
    assert input_data.description == "Test Item"
    assert input_data.brand == "TestBrand"
    assert input_data.model == "TestModel"
    assert input_data.master_sale_price == Decimal("100.00")
    assert input_data.barcode == "1234567890123"


def test_item_creation_input_optional_fields():
    """ItemCreationInput should work with only required fields."""
    input_data = ItemCreationInput(
        item_code=None,
        description="Minimal Item",
        category_id=uuid.uuid4(),
        item_type_id=uuid.uuid4(),
    )
    assert input_data.item_code is None
    assert input_data.description == "Minimal Item"
    assert input_data.brand is None
    assert input_data.model is None
    assert input_data.master_sale_price is None
    assert input_data.barcode is None


def test_item_creation_result_dataclass():
    """ItemCreationResult should hold item and barcodes tuple."""
    from app.models.master import Item, ItemBarcode
    item = Item(id=uuid.uuid4(), item_code="TEST", description="Test")
    barcode = ItemBarcode(id=uuid.uuid4(), item_id=item.id, barcode="123", is_primary=True)
    result = ItemCreationResult(item=item, barcodes=(barcode,))
    assert result.item == item
    assert result.barcodes == (barcode,)


def test_item_creation_error_is_value_error():
    """ItemCreationError should be a ValueError for exception handling."""
    assert issubclass(ItemCreationError, ValueError)
    try:
        raise ItemCreationError("test error")
    except ValueError:
        pass


def test_item_service_requires_session():
    """ItemService should require a session at construction."""
    from sqlalchemy.orm import Session
    # This is a static check - just verify the signature
    import inspect
    sig = inspect.signature(ItemService.__init__)
    assert "session" in sig.parameters
    # Annotation may be string due to from __future__ import annotations
    ann = sig.parameters["session"].annotation
    assert ann == Session or ann == "Session"


def test_create_item_from_schema_signature():
    """create_item_from_schema should accept schema and context."""
    import inspect
    sig = inspect.signature(create_item_from_schema)
    params = list(sig.parameters.keys())
    assert "session" in params
    assert "payload" in params
    assert "branch_id" in params
    assert "actor_user_id" in params
    assert "is_admin" in params


def test_item_creation_input_from_schema():
    """Converting ItemCreateIn to ItemCreationInput should preserve data."""
    payload = ItemCreateIn(
        item_code="ITEM-000001",
        description="Test Item",
        category_id=uuid.uuid4(),
        item_type_id=uuid.uuid4(),
        brand="TestBrand",
        model="TestModel",
        master_sale_price=Decimal("100.00"),
        barcode="1234567890123",
    )
    input_data = ItemCreationInput(
        item_code=payload.item_code,
        description=payload.description,
        category_id=payload.category_id,
        item_type_id=payload.item_type_id,
        brand=payload.brand,
        model=payload.model,
        master_sale_price=payload.master_sale_price,
        barcode=payload.barcode,
    )
    assert input_data.item_code == payload.item_code
    assert input_data.description == payload.description
    assert input_data.category_id == payload.category_id
    assert input_data.item_type_id == payload.item_type_id
    assert input_data.brand == payload.brand
    assert input_data.model == payload.model
    assert input_data.master_sale_price == payload.master_sale_price
    assert input_data.barcode == payload.barcode