from pathlib import Path


def test_purchase_model_has_supplier_field():
    """Purchase model should have supplier_id field."""
    model_code = Path(__file__).parents[1] / "app" / "models" / "inventory.py"
    content = model_code.read_text()
    
    assert "supplier_id" in content
    assert "ForeignKey(\"suppliers.id\"" in content
    assert "supplier = relationship(\"Supplier\")" in content


def test_purchase_service_accepts_supplier_id():
    """PurchaseService.create_purchase should accept supplier_id parameter."""
    service_code = Path(__file__).parents[1] / "app" / "services" / "purchases.py"
    content = service_code.read_text()
    
    assert "supplier_id: uuid.UUID | None = None" in content
    assert "supplier_id=supplier_id if admin_side else None" in content


def test_supplier_assignment_is_admin_only():
    """Supplier assignment should be Admin-only."""
    service_code = Path(__file__).parents[1] / "app" / "services" / "purchases.py"
    content = service_code.read_text()
    
    assert "if not admin_side:" in content
    assert 'raise ValueError("Supplier assignment is Admin-only")' in content


def test_purchase_route_enforces_admin_for_supplier():
    """Purchase route should only pass supplier_id for Admin users."""
    route_code = Path(__file__).parents[1] / "app" / "api" / "routes" / "purchases.py"
    content = route_code.read_text()
    
    assert 'supplier_id=payload.supplier_id if user.role.code.upper() == "ADMIN" else None' in content


def test_purchase_history_includes_supplier():
    """Purchase history should include supplier information."""
    route_code = Path(__file__).parents[1] / "app" / "api" / "routes" / "purchases.py"
    content = route_code.read_text()
    
    assert ".outerjoin(Supplier, Supplier.id == Purchase.supplier_id)" in content
    assert "supplier_name=s.name if s else None" in content


def test_supplier_assignment_is_audited():
    """Supplier assignment should be audited."""
    route_code = Path(__file__).parents[1] / "app" / "api" / "routes" / "purchases.py"
    content = route_code.read_text()
    
    assert "PURCHASE_SUPPLIER_CORRECTED" in content
    assert "before_json={'supplier_id':old}" in content
    assert "after_json={'supplier_id':str(purchase.supplier_id)" in content


def test_supplier_assignment_endpoint_exists():
    """Admin should have a dedicated endpoint to set supplier on existing purchase."""
    route_code = Path(__file__).parents[1] / "app" / "api" / "routes" / "purchases.py"
    content = route_code.read_text()
    
    assert "@router.put('/{purchase_id}/supplier')" in content
    assert "require_admin_reauth" in content


def test_supplier_validation_checks_active():
    """Service should validate that supplier is active."""
    service_code = Path(__file__).parents[1] / "app" / "services" / "purchases.py"
    content = service_code.read_text()
    
    assert "Supplier.is_active.is_(True)" in content
    assert 'raise ValueError("Active supplier not found")' in content


def test_purchase_schema_includes_supplier_id():
    """PurchaseCreateIn schema should include supplier_id field."""
    schema_code = Path(__file__).parents[1] / "app" / "schemas" / "purchases.py"
    content = schema_code.read_text()
    
    assert "supplier_id: UUID | None = None" in content


def test_purchase_history_schema_includes_supplier():
    """PurchaseHistoryLineOut schema should include supplier fields."""
    schema_code = Path(__file__).parents[1] / "app" / "schemas" / "purchases.py"
    content = schema_code.read_text()
    
    assert "supplier_id: UUID | None" in content
    assert "supplier_name: str | None" in content
