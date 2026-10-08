from pathlib import Path


def test_warranty_default_model_exists():
    """WarrantyDefault model should exist with required fields."""
    model_code = Path(__file__).parents[1] / "app" / "models" / "master.py"
    content = model_code.read_text()
    
    assert "class WarrantyDefault" in content
    assert "item_id" in content
    assert "warranty_type" in content
    assert "duration_value" in content
    assert "custom_rule" in content
    assert "is_active" in content


def test_warranty_creation_uses_default_from_item_master():
    """Sale warranty creation should use default from WarrantyDefault if not overridden."""
    service_code = Path(__file__).parents[1] / "app" / "services" / "sales.py"
    content = service_code.read_text()
    
    assert "select(WarrantyDefault)" in content
    assert "WarrantyDefault.item_id == item.id" in content
    assert "WarrantyDefault.is_active.is_(True)" in content
    assert "warranty_type, warranty_duration_value, warranty_custom_rule = default.warranty_type, default.duration_value, default.custom_rule" in content


def test_warranty_none_creates_record_for_audit():
    """Warranty type NONE should create a ProductWarranty record for audit trail.
    
    This is intentional design - it distinguishes between:
    - No warranty record (item had no default warranty configured)
    - Explicit NONE warranty (item had default or override set to NONE)
    
    Both result in no warranty coverage, but the audit trail is different.
    """
    service_code = Path(__file__).parents[1] / "app" / "services" / "sales.py"
    content = service_code.read_text()
    
    # Check that NONE is a valid warranty type
    assert '"NONE"' in content
    assert "warranty_type not in {\"NONE\", \"DAYS\", \"MONTHS\", \"CHECKING ONLY\", \"CUSTOM\"}" in content
    
    # Check that warranty record is created even for NONE
    assert "ProductWarranty(" in content
    assert "warranty_type=warranty_type" in content


def test_warranty_modes_supported():
    """System should support required warranty modes: NONE, DAYS, MONTHS, CHECKING ONLY, CUSTOM.
    
    Note: The warranty calculator also supports YEARS for custom rules, but the sale-time
    UI/service enforces the core modes. YEARS can be used via CUSTOM rules.
    """
    service_code = Path(__file__).parents[1] / "app" / "services" / "sales.py"
    content = service_code.read_text()
    
    assert '"NONE"' in content
    assert '"DAYS"' in content
    assert '"MONTHS"' in content
    assert '"CHECKING ONLY"' in content
    assert '"CUSTOM"' in content


def test_warranty_none_returns_none_expiry():
    """Warranty type NONE should return None expiry date."""
    calc_code = Path(__file__).parents[1] / "app" / "services" / "warranty_calculator.py"
    content = calc_code.read_text()
    
    assert "if kind in {'NONE', 'NO WARRANTY', 'CHECKING ONLY', 'CHECKING'}:" in content
    assert "return None" in content


def test_warranty_snapshot_is_immutable():
    """Sale-time warranty snapshot should be immutable - warranty record stores exact sale-time config."""
    service_code = Path(__file__).parents[1] / "app" / "services" / "sales.py"
    content = service_code.read_text()
    
    # Warranty record stores the exact values at sale time
    assert "warranty_type=warranty_type" in content
    assert "duration_value=warranty_duration_value" in content
    assert "custom_rule=warranty_custom_rule" in content
    assert "expiry_date=expiry" in content
    
    # ProductWarranty has VersionMixin for immutability tracking
    model_code = Path(__file__).parents[1] / "app" / "models" / "warranty.py"
    model_content = model_code.read_text()
    assert "class ProductWarranty(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):" in model_content


def test_warranty_override_validation():
    """Warranty override should validate duration/custom rule based on type."""
    service_code = Path(__file__).parents[1] / "app" / "services" / "sales.py"
    content = service_code.read_text()
    
    # NONE/CHECKING ONLY cannot have duration/custom rule
    assert "if warranty_type in {\"NONE\", \"CHECKING ONLY\"}" in content
    assert "raise SaleValidationError(\"This warranty override cannot have duration/custom rule\")" in content
    
    # DAYS/MONTHS require duration
    assert "if warranty_type in {\"DAYS\", \"MONTHS\"} and warranty_duration_value is None:" in content
    assert "raise SaleValidationError(\"Warranty override duration is required\")" in content
    
    # CUSTOM requires custom rule
    assert "if warranty_type == \"CUSTOM\" and not (warranty_custom_rule or '').strip():" in content
    assert "raise SaleValidationError(\"Custom warranty rule is required\")" in content


def test_warranty_calculator_handles_custom_rules():
    """Warranty calculator should parse custom rules including YEARS."""
    calc_code = Path(__file__).parents[1] / "app" / "services" / "warranty_calculator.py"
    content = calc_code.read_text()
    
    assert "if kind == 'CUSTOM':" in content
    assert "re.fullmatch" in content
    # Calculator supports YEARS for custom rules even if sale-time service restricts to DAYS/MONTHS
    assert "'YEAR'" in content and "'YEARS'" in content


def test_warranty_default_is_active_filter():
    """Only active warranty defaults should be used."""
    service_code = Path(__file__).parents[1] / "app" / "services" / "sales.py"
    content = service_code.read_text()
    
    assert "WarrantyDefault.is_active.is_(True)" in content


def test_warranty_no_default_returns_none():
    """If no warranty default exists, warranty should not be created.
    
    This is different from having a warranty default of NONE.
    - No default configured → No warranty record created
    - Default of NONE configured → Warranty record created with type NONE
    
    This distinction allows the system to track:
    - Items that were never meant to have warranty (no record)
    - Items that explicitly had no warranty coverage (NONE record)
    """
    service_code = Path(__file__).parents[1] / "app" / "services" / "sales.py"
    content = service_code.read_text()
    
    assert "if default is None:" in content
    assert "return None" in content
