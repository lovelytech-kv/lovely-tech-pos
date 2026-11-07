"""Read/write session timeout settings from system_settings table."""
from __future__ import annotations
from datetime import datetime, timezone
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.settings import SystemSetting


KEYS = {
    'admin_minutes': 'session_timeout_admin_minutes',
    'cashier_minutes': 'session_timeout_cashier_minutes',
    'admin_hours': 'session_absolute_timeout_admin_hours',
    'cashier_hours': 'session_absolute_timeout_cashier_hours',
}


def _coerce_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def get_session_settings(db: Session) -> dict:
    """Return current timeouts (falls back to env config if DB row missing)."""
    rows = db.scalars(select(SystemSetting)).all()
    m = {r.key: r.value for r in rows}
    return {
        'admin_minutes': _coerce_int(m.get(KEYS['admin_minutes']), settings.session_timeout_admin_minutes),
        'cashier_minutes': _coerce_int(m.get(KEYS['cashier_minutes']), settings.session_timeout_cashier_minutes),
        'admin_hours': _coerce_int(m.get(KEYS['admin_hours']), settings.session_absolute_timeout_admin_hours),
        'cashier_hours': _coerce_int(m.get(KEYS['cashier_hours']), settings.session_absolute_timeout_cashier_hours),
    }


def save_session_settings(db: Session, values: dict, updated_by: uuid.UUID | None) -> dict:
    now = datetime.now(timezone.utc)
    for label, key in KEYS.items():
        if label not in values:
            continue
        val = int(values[label])
        row = db.get(SystemSetting, key)
        if row is None:
            db.add(SystemSetting(key=key, value=str(val), updated_at=now, updated_by=updated_by))
        else:
            row.value = str(val)
            row.updated_at = now
            row.updated_by = updated_by
    db.flush()
    return get_session_settings(db)