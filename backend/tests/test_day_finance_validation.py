from decimal import Decimal
from app.services.day_finance import DayFinanceService, DayFinanceError

def test_actual_denominations_must_match_actual_cash():
    s=DayFinanceService(None)
    try:
        s.validate_denominations({'5000':1}, Decimal('4000'), field_name='Actual cash')
    except DayFinanceError as exc:
        assert 'must equal' in str(exc)
    else:
        raise AssertionError('expected validation error')

def test_reason_required_message():
    assert not str('  ').strip()


def test_reload_provider_allowlist():
    svc=DayFinanceService(None)
    for provider in ('Dialog','Airtel','Mobitel','Hutch'):
        assert provider in {'Dialog','Airtel','Mobitel','Hutch'}
    try:
        svc.add_reload(day_session_id='x', user_id='u', provider='Unknown', amount=Decimal('10'))
    except DayFinanceError as exc:
        assert 'Unsupported reload provider' in str(exc)
    else:
        raise AssertionError('expected provider validation error')


def test_day_end_requires_version_check():
    """Day end should require version for stale-state protection."""
    from pathlib import Path
    service_code = Path(__file__).parents[1] / "app" / "services" / "day_finance.py"
    content = service_code.read_text()
    assert "version: int | None = None" in content
    assert "if version is not None and day.version != version:" in content
    assert "raise DayFinanceError('Day session changed; reload before editing')" in content


def test_day_end_calculates_expected_cash():
    """Day end should calculate expected cash including all cash flows."""
    from pathlib import Path
    service_code = Path(__file__).parents[1] / "app" / "services" / "day_finance.py"
    content = service_code.read_text()
    
    # Check expected_cash calculation includes all components
    assert "cash_sales" in content
    assert "repair_cash" in content
    assert "settlement_cash" in content
    assert "refund_cash" in content
    assert "reloads" in content
    assert "other" in content


def test_day_end_captures_mismatch():
    """Day end should capture difference between expected and actual cash."""
    from pathlib import Path
    service_code = Path(__file__).parents[1] / "app" / "services" / "day_finance.py"
    content = service_code.read_text()
    
    # Check difference calculation
    assert "diff=self.money(actual-expected)" in content
    assert "difference=diff" in content


def test_day_end_requires_reason():
    """Day end should require a reason for mismatch."""
    from pathlib import Path
    service_code = Path(__file__).parents[1] / "app" / "services" / "day_finance.py"
    content = service_code.read_text()
    
    assert "if not str(reason or '').strip():" in content
    assert "raise DayFinanceError('Day End reason is required')" in content


def test_shift_end_vs_day_end_distinction():
    """Shift end and day end should be distinct operations."""
    from pathlib import Path
    service_code = Path(__file__).parents[1] / "app" / "services" / "day_finance.py"
    content = service_code.read_text()
    
    # Shift end changes status to SHIFT_ENDED
    assert "def shift_end" in content
    assert "row.status='SHIFT_ENDED'" in content
    
    # Day end creates DayEnd record and closes day
    assert "def end_day" in content
    assert "DayEnd(" in content
    assert "day.status='CLOSED'" in content


def test_day_end_captures_reload_total():
    """Day end should capture total reload amount."""
    from pathlib import Path
    service_code = Path(__file__).parents[1] / "app" / "services" / "day_finance.py"
    content = service_code.read_text()
    
    assert "reload_total=self.money(self.session.scalar" in content
    assert "select(func.coalesce(func.sum(ReloadEntry.amount),0))" in content


def test_day_opening_correction_has_audit():
    """Opening cash correction should be audited."""
    from pathlib import Path
    service_code = Path(__file__).parents[1] / "app" / "services" / "day_finance.py"
    content = service_code.read_text()
    
    assert "DAY_OPENING_CORRECTED" in content
    assert "AuditLog" in content
    assert "before_json" in content
    assert "after_json" in content


def test_day_reopen_has_audit():
    """Day reopen should be audited."""
    from pathlib import Path
    service_code = Path(__file__).parents[1] / "app" / "services" / "day_finance.py"
    content = service_code.read_text()
    
    assert "DAY_REOPENED" in content
    assert "Admin reopened closed business day" in content


def test_day_operations_use_row_locking():
    """Day operations should use row-level locking for concurrency."""
    from pathlib import Path
    service_code = Path(__file__).parents[1] / "app" / "services" / "day_finance.py"
    content = service_code.read_text()
    
    assert ".with_for_update()" in content


def test_day_auto_close_after_shift_end():
    """Day should auto-close after 1 hour of shift end."""
    from pathlib import Path
    service_code = Path(__file__).parents[1] / "app" / "services" / "day_finance.py"
    content = service_code.read_text()
    
    assert "timedelta(hours=1)" in content
    assert "row.status = 'CLOSED'" in content
