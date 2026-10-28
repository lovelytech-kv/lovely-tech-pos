"""After an Admin resets a cashier's password the cashier may only change it (then everything works again)."""
import pytest

from tests.test_e2e_requirements import PASSWORD_ADMIN, _db_available, ctx  # noqa: F401

pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL is not reachable")


def test_reset_forces_password_change_before_any_other_call(ctx):
    c = ctx["c"]
    me = c.get("/api/v1/auth/me", headers=ctx["C"]).json()
    r = c.post("/api/v1/admin/users/reset-password", headers=ctx["A"],
               json={"user_id": me["user_id"], "admin_password": PASSWORD_ADMIN, "new_password": "TempReset#2026Aa"})
    assert r.status_code == 200, r.text

    login = c.post("/api/v1/auth/login", json={"username": me["username"], "password": "TempReset#2026Aa"})
    assert login.status_code == 200 and login.json()["must_change_password"] is True
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}

    blocked = c.get("/api/v1/day/status", headers=h)
    assert blocked.status_code == 403 and "PASSWORD_CHANGE_REQUIRED" in blocked.text
    assert c.get("/api/v1/auth/me", headers=h).status_code == 200

    same = c.post("/api/v1/auth/change-password", headers=h, json={"current_password": "TempReset#2026Aa", "new_password": "TempReset#2026Aa"})
    assert same.status_code == 400
    done = c.post("/api/v1/auth/change-password", headers=h, json={"current_password": "TempReset#2026Aa", "new_password": "MyOwnNew#2026Bb"})
    assert done.status_code == 200 and done.json()["must_change_password"] is False
    assert c.get("/api/v1/day/status", headers=h).status_code == 200
    again = c.post("/api/v1/auth/login", json={"username": me["username"], "password": "MyOwnNew#2026Bb"})
    assert again.status_code == 200 and again.json()["must_change_password"] is False
