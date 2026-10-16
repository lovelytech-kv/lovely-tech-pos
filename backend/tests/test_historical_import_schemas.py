import pytest
from decimal import Decimal
from datetime import datetime
from app.schemas.historical_import import ImportItemRecord, ImportPurchaseRecord, ImportSaleRecord

def test_import_item_record_parsing():
    raw_data = {
        "ITEM CODE": "LVT0001",
        "DESCRIPTION": "12V 2A CHARGER",
        "Brand": "MULTI",
        "CATEGORY 1": "CHARGER & CABLE",
        "WARRANTY": "3 MONTH",
        "SALE PRICE": "950"
    }
    record = ImportItemRecord.model_validate(raw_data)
    assert record.item_code == "LVT0001"
    assert record.description == "12V 2A CHARGER"
    assert record.brand == "MULTI"
    assert record.sale_price == Decimal("950")

def test_import_purchase_record_parsing():
    raw_data = {
        "DATE": "2024-10-01 00:00:00",
        "ITEM CODE": "LVT0174",
        "UNIT PRICE": "80.50",
        "QUANTITY": 18
    }
    record = ImportPurchaseRecord.model_validate(raw_data)
    assert record.item_code == "LVT0174"
    assert record.quantity == 18
    assert record.unit_price == Decimal("80.50")

def test_import_sale_record_parsing():
    raw_data = {
        "DATE": "2024-10-01 00:00:00",
        "ITEM CODE": "LVT0394",
        "SALE PRICE": "900",
        "QUANTITY": 4
    }
    record = ImportSaleRecord.model_validate(raw_data)
    assert record.item_code == "LVT0394"
    assert record.quantity == 4
    assert record.sale_price == Decimal("900")
