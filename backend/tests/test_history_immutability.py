from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_history_immutability_migration_protects_append_only_tables():
    source = (ROOT / "backend/alembic/versions/0023_history_immutability.py").read_text()
    for table in ("target_progress_snapshots", "record_versions", "document_events", "login_events"):
        assert table in source
    assert "trg_{table}_immutable_update" in source
    assert "trg_{table}_immutable_delete" in source
    assert "RAISE EXCEPTION 'historical record is append-only" in source


def test_existing_audit_log_is_db_trigger_protected():
    source = (ROOT / "backend/alembic/versions/0014_audit_immutability.py").read_text()
    assert "trg_audit_immutable_update" in source
    assert "trg_audit_immutable_delete" in source
    assert "RAISE EXCEPTION 'audit_log is append-only'" in source
