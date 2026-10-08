from __future__ import annotations
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
import re

class WarrantyCalculationError(ValueError):
    pass

def calculate_expiry(start: date, warranty_type: str, duration_value: int | None = None, custom_rule: str | None = None) -> date | None:
    kind = (warranty_type or '').strip().upper()
    if kind in {'NONE', 'NO WARRANTY', 'CHECKING ONLY', 'CHECKING'}:
        return None
    if kind in {'DAY','DAYS'}:
        if duration_value is None or duration_value < 0: raise WarrantyCalculationError('Warranty duration is required')
        return start + timedelta(days=duration_value)
    if kind in {'MONTH','MONTHS'}:
        if duration_value is None or duration_value < 0: raise WarrantyCalculationError('Warranty duration is required')
        month = start.month - 1 + duration_value
        year = start.year + month // 12
        month = month % 12 + 1
        return date(year, month, min(start.day, monthrange(year, month)[1]))
    if kind in {'YEAR','YEARS'}:
        if duration_value is None or duration_value < 0: raise WarrantyCalculationError('Warranty duration is required')
        try: return start.replace(year=start.year + duration_value)
        except ValueError: return start.replace(year=start.year + duration_value, day=28)
    if kind == 'CUSTOM':
        rule=(custom_rule or '').strip().upper()
        m=re.fullmatch(r'(\d+)\s*(DAY|DAYS|MONTH|MONTHS|YEAR|YEARS)', rule)
        if not m: raise WarrantyCalculationError('Unsupported custom warranty rule')
        return calculate_expiry(start, m.group(2), int(m.group(1)))
    raise WarrantyCalculationError('Unsupported warranty type')

def warranty_status(start: date, expiry: date | None, today: date) -> str:
    if expiry is None:
        return 'CHECKING_ONLY' if start <= today else 'NOT_STARTED'
    if today < start: return 'NOT_STARTED'
    if today <= expiry: return 'ACTIVE'
    return 'EXPIRED'
