from datetime import date
from app.services.warranty_calculator import calculate_expiry


def test_custom_warranty_rule_is_calculated_at_sale_time():
    assert calculate_expiry(date(2026, 10, 2), "CUSTOM", custom_rule="45 DAYS") == date(2026, 11, 16)
