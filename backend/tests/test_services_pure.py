from decimal import Decimal
from app.services.reports import SalesSummary
from app.services.day_finance import DayFinanceService

def test_money_rounding():
    assert DayFinanceService.money(Decimal('10.005')) == Decimal('10.01')

def test_summary_dataclass():
    s=SalesSummary(Decimal('100'),Decimal('50'),Decimal('30'),Decimal('20'),2,Decimal('60'),Decimal('40'),Decimal('5'),Decimal('2'),Decimal('37'))
    assert s.net_profit == Decimal('37')


def test_repair_state_machine_allowed_transitions():
    from app.services.repairs import RepairService
    assert "CHECKING" in RepairService.ALLOWED_TRANSITIONS["RECEIVED"]
    assert "READY" in RepairService.ALLOWED_TRANSITIONS["REPAIRING"]
    assert "DELIVERED" in RepairService.ALLOWED_TRANSITIONS["READY"]
    assert RepairService.ALLOWED_TRANSITIONS["DELIVERED"] == set()
    assert RepairService.ALLOWED_TRANSITIONS["CANCELLED"] == set()

def test_repair_terminal_states_and_delivery_path():
    from app.services.repairs import RepairService
    assert RepairService.ALLOWED_TRANSITIONS['READY'] == {'DELIVERED', 'RETURNED TO CUSTOMER', 'CANCELLED'}
    assert 'RETURNED TO CUSTOMER' in RepairService.STATUSES
    assert RepairService.ALLOWED_TRANSITIONS['RETURNED TO CUSTOMER'] == set()
