"""Focused tests: CreditSettlement, StockAdjustment, DamageLossRecord version locking.

Static source assertions, matching the existing test style in this repo
(test_day_finance_validation.py, test_cash_only_calculations.py).
"""

from pathlib import Path

BACKEND = Path(__file__).parents[1]
SALES_MODEL = (BACKEND / "app" / "models" / "sales.py").read_text()
INVENTORY_MODEL = (BACKEND / "app" / "models" / "inventory.py").read_text()
REPAIRS = (BACKEND / "app" / "services" / "repairs.py").read_text()
OPS = (BACKEND / "app" / "api" / "routes" / "operations.py").read_text()
MIGRATION = (BACKEND / "alembic" / "versions" / "0029_credit_settlement_version.py").read_text()


# ---------------------------------------------------------------------------
# CreditSettlement
# ---------------------------------------------------------------------------

def test_credit_settlement_model_carries_version_mixin():
    assert "class CreditSettlement(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):" in SALES_MODEL


def test_credit_settlement_migration_adds_version_column():
    assert 'op.add_column(' in MIGRATION
    assert '"credit_settlements"' in MIGRATION
    assert 'sa.Column("version"' in MIGRATION
    assert 'server_default=sa.text("1")' in MIGRATION


def test_credit_settlement_migration_is_chain_head_after_0028():
    assert 'revision = "0029_credit_settlement_version"' in MIGRATION
    assert 'down_revision = "0028_sale_return_exchange_version_lock"' in MIGRATION


def test_credit_settlement_settle_creates_with_default_version():
    settlements = (BACKEND / "app" / "services" / "settlements.py").read_text()
    # CreditSettlement is created without an explicit version; VersionMixin
    # default + migration server_default both set it to 1.
    assert "CreditSettlement(branch_id=branch_id" in settlements


# ---------------------------------------------------------------------------
# StockAdjustment
# ---------------------------------------------------------------------------

def test_stock_adjustment_model_carries_version_mixin():
    assert "class StockAdjustment(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):" in INVENTORY_MODEL


def test_stock_adjustment_service_creates_rows_with_default_version():
    stock_control = (BACKEND / "app" / "services" / "stock_control.py").read_text()
    assert "StockAdjustment(branch_id=branch_id" in stock_control


# ---------------------------------------------------------------------------
# DamageLossRecord
# ---------------------------------------------------------------------------

def test_damage_loss_record_model_carries_version_mixin():
    assert "class DamageLossRecord(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):" in INVENTORY_MODEL


def test_damage_loss_review_requires_version():
    assert "version: int | None = None" in REPAIRS.split("def review_damaged_part")[1].split("def add_payment")[0]
    assert "if version is None: raise RepairValidationError(\"Damage loss record version is required; reload before editing\")" in REPAIRS


def test_damage_loss_review_rejects_stale_version():
    assert "if loss.version != version: raise RepairValidationError(\"Damage loss record changed; reload before editing\")" in REPAIRS


def test_damage_loss_review_increments_version():
    assert "loss.version += 1" in REPAIRS.split("def review_damaged_part")[1].split("def add_payment")[0]


def test_damage_loss_review_returns_version():
    assert "\"version\":loss.version}" in REPAIRS.split("def review_damaged_part")[1].split("def add_payment")[0]


def test_damage_loss_review_route_passes_version():
    assert "version=payload.version" in OPS.split("def repair_part_damage_review")[1]