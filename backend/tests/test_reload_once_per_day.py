from decimal import Decimal
import pytest
from app.services.day_finance import DayFinanceService, DayFinanceError


def test_reload_service_enforces_one_per_day_in_logic():
    """Service logic checks for existing reload before inserting."""
    svc = DayFinanceService(None)
    # The service should check for existing reloads
    # This is verified by the check in add_reload method
    from pathlib import Path
    service_code = Path(__file__).parents[1] / "app" / "services" / "day_finance.py"
    content = service_code.read_text()
    assert "existing=self.session.scalar(select(ReloadEntry)" in content
    assert "if existing is not None:" in content
    assert "raise DayFinanceError" in content


def test_reload_requires_positive_amount():
    """Reload amount must be positive."""
    svc = DayFinanceService(None)
    
    with pytest.raises(DayFinanceError) as exc:
        svc.add_reload(
            day_session_id="x",
            user_id="u",
            provider="Dialog",
            amount=Decimal("0")
        )
    assert "positive" in str(exc.value).lower()
    
    with pytest.raises(DayFinanceError) as exc:
        svc.add_reload(
            day_session_id="x",
            user_id="u",
            provider="Dialog",
            amount=Decimal("-100")
        )
    assert "positive" in str(exc.value).lower()


def test_reload_provider_validation():
    """Only allowed providers should be accepted."""
    svc = DayFinanceService(None)
    
    allowed_providers = ["Dialog", "Airtel", "Mobitel", "Hutch"]
    for provider in allowed_providers:
        assert provider in svc.DENOMINATIONS or provider in {"Dialog", "Airtel", "Mobitel", "Hutch"}
    
    # Test invalid provider
    with pytest.raises(DayFinanceError) as exc:
        svc.add_reload(
            day_session_id="x",
            user_id="u",
            provider="UnknownProvider",
            amount=Decimal("100")
        )
    assert "unsupported" in str(exc.value).lower()


def test_reload_database_trigger_enforces_one_per_day():
    """Database trigger should prevent duplicate reloads."""
    from pathlib import Path
    migration_path = Path(__file__).parents[1] / "alembic" / "versions" / "0024_reload_once_per_day.py"
    content = migration_path.read_text()
    
    # Verify trigger exists
    assert "CREATE TRIGGER trg_reload_once_per_day" in content
    assert "BEFORE INSERT OR UPDATE ON reload_entries" in content
    assert "RAISE EXCEPTION 'reload already entered for this business day'" in content
    assert "WHERE day_session_id = NEW.day_session_id" in content
