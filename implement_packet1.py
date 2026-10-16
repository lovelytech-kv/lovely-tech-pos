import os, subprocess

root = r"C:\Lovely Tech POS"
schema_path = os.path.join(root, "backend", "app", "schemas", "historical_import.py")
test_path = os.path.join(root, "backend", "tests", "test_historical_import_schemas.py")

schema_code = """from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal

class ImportItemRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    item_code: str = Field(alias="ITEM CODE")
    description: str = Field(alias="DESCRIPTION")
    category: Optional[str] = Field(None, alias="CATEGORY 1")
    brand: Optional[str] = Field(None, alias="Brand")
    warranty: Optional[str] = Field(None, alias="WARRANTY")
    sale_price: Optional[Decimal] = Field(None, alias="SALE PRICE")

class ImportPurchaseRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    date: datetime = Field(alias="DATE")
    item_code: str = Field(alias="ITEM CODE")
    unit_price: Decimal = Field(alias="UNIT PRICE")
    quantity: int = Field(alias="QUANTITY")

class ImportSaleRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    date: datetime = Field(alias="DATE")
    item_code: str = Field(alias="ITEM CODE")
    sale_price: Decimal = Field(alias="SALE PRICE")
    quantity: int = Field(alias="QUANTITY")
"""

test_code = """import pytest
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
"""

# Create files safely
with open(schema_path, 'w', encoding='utf-8') as f:
    f.write(schema_code)

with open(test_path, 'w', encoding='utf-8') as f:
    f.write(test_code)

print("Created app/schemas/historical_import.py")
print("Created tests/test_historical_import_schemas.py")

# Run pytest for the newly created test
backend_dir = os.path.join(root, "backend")
pytest_exe = os.path.join(backend_dir, ".venv", "Scripts", "pytest.exe")
if not os.path.exists(pytest_exe): pytest_exe = "pytest"

print("\n========== RUNNING TESTS FOR PACKET 1 ==========")
env = os.environ.copy()
env["PYTHONPATH"] = backend_dir
res = subprocess.run([pytest_exe, "-v", "tests/test_historical_import_schemas.py"], cwd=backend_dir, capture_output=True, text=True, env=env)
print(res.stdout)
if res.stderr:
    print(res.stderr)