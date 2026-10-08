from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def source(rel: str) -> str:
    return (ROOT / rel).read_text()


def test_mutable_financial_flows_require_stale_version_guards():
    routes = source('backend/app/api/routes/operations.py')
    purchases = source('backend/app/api/routes/purchases.py')
    warranty = source('backend/app/api/routes/warranty.py')
    admin = source('backend/app/api/routes/admin.py')
    assert "Repair version is required; reload the record" in routes
    assert "Day version is required; reload the record" in routes
    assert "Approval version is required; reload the record" in routes
    assert "Purchase line version is required; reload the record" in purchases
    assert "Purchase version is required; reload the record" in purchases
    assert "Warranty claim version is required; reload the claim" in warranty
    assert "User version is required; reload the record" in admin


def test_version_is_advanced_after_controlled_state_changes():
    repairs = source('backend/app/services/repairs.py')
    warranty = source('backend/app/services/warranty.py')
    day = source('backend/app/services/day_finance.py')
    approval = source('backend/app/services/approvals.py')
    assert 'repair.version += 1' in repairs
    assert 'claim.version += 1' in warranty
    assert 'day.version += 1' in day
    assert 'row.version += 1' in approval


def test_audit_and_history_tables_remain_database_immutable():
    migrations = '\n'.join(p.read_text() for p in (ROOT / 'backend/alembic/versions').glob('*.py'))
    assert 'audit_log' in migrations and 'trg_audit_immutable_update' in migrations
    assert 'target_progress_snapshots' in migrations
    assert 'record_versions' in migrations
    assert 'document_events' in migrations
    assert 'login_events' in migrations
