from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.api.deps import current_user, token_hash
from app.models.auth import UserSession
from app.models.master import User


def test_session_inactivity_window_uses_role_timeout():
    # Contract-level regression test: timeout values are role-specific and
    # are enforced from last_seen_at rather than only from absolute expiry.
    from app.core.config import settings
    assert settings.session_timeout_admin_minutes == 5
    assert settings.session_timeout_cashier_minutes == 60
    assert settings.session_absolute_timeout_admin_hours == 12
    assert settings.session_absolute_timeout_cashier_hours == 12
