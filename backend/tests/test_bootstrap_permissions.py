"""Every permission enforced by a route must be created by the security bootstrap, and the
Cashier role must receive the permissions the Requirements v2.0 baseline grants it."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = (ROOT / "scripts" / "bootstrap_security.py").read_text(encoding="utf-8")


def _route_permission_codes():
    codes = set()
    for path in (ROOT / "backend" / "app").rglob("*.py"):
        codes.update(re.findall(r"require_permission\(['\"]([A-Z_]+)['\"]\)", path.read_text(encoding="utf-8")))
    return codes


def test_bootstrap_defines_every_route_permission():
    defined = set(re.findall(r"\('([A-Z_]+)',\s*'[^']+',", BOOTSTRAP))
    assert _route_permission_codes() <= defined


def test_cashier_has_read_only_item_access():
    # Manager decision (Session 3A, C6 / Option A): Cashier can view the item
    # master but must not create or edit items.
    cashier_block = re.search(r"cashier_codes=\{([^}]*)\}", BOOTSTRAP).group(1)
    assert "'ITEM_EDIT'" not in cashier_block
    assert "'STOCK_VIEW'" in cashier_block
    assert "'PURCHASE_ENTRY'" in cashier_block
    # ...and never cost entry or Admin controls.
    for forbidden in ("PURCHASE_COST", "STOCK_ADJUST", "ADMIN_PANEL", "BACKUP_MANAGE", "WARRANTY_DECIDE"):
        assert f"'{forbidden}'" not in cashier_block
