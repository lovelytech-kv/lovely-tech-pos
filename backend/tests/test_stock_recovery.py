from decimal import Decimal
from app.services.stock_control import StockControlService, StockControlError
from app.services.targets import TargetService

def test_stock_adjust_rejects_zero():
    class Dummy: pass
    try: StockControlService(Dummy()).adjust(branch_id=None,item_id=None,quantity_delta=Decimal('0'),reason='x',user_id=None)
    except StockControlError as e: assert 'zero' in str(e).lower()
