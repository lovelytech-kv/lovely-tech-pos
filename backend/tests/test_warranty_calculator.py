from datetime import date
from app.services.warranty_calculator import calculate_expiry, warranty_status

def test_warranty_days_and_exact_status():
    start=date(2026,9,24); expiry=calculate_expiry(start,'DAYS',7)
    assert expiry == date(2026,10,1)
    assert warranty_status(start,expiry,date(2026,10,1)) == 'ACTIVE'
    assert warranty_status(start,expiry,date(2026,10,2)) == 'EXPIRED'

def test_warranty_month_end_is_clamped():
    assert calculate_expiry(date(2026,1,31),'MONTHS',1) == date(2026,2,28)

def test_checking_only_has_no_expiry():
    expiry=calculate_expiry(date(2026,9,24),'CHECKING ONLY')
    assert expiry is None
    assert warranty_status(date(2026,9,24),expiry,date(2026,9,24)) == 'CHECKING_ONLY'
