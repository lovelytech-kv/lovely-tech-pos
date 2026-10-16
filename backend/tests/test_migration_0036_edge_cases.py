"""Focused tests for migration 0036 edge cases: empty batches and mixed row types.

These tests require an isolated PostgreSQL test database.
They verify that the migration handles legacy data correctly without
silently fabricating types or arbitrarily choosing row types.

Run with: pytest tests/test_migration_0036_edge_cases.py -v --tb=short
Requires: PostgreSQL test database (set TEST_DATABASE_URL env var)
"""

import os
import uuid
import json
from datetime import datetime, timezone

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

# Require explicit PostgreSQL test database
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    pytest.skip(
        "TEST_DATABASE_URL not set; skipping PostgreSQL migration tests",
        allow_module_level=True,
    )

# Prevent env.py from overriding the test URL with settings.database_url
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

alembic_cfg = Config("C:/Lovely Tech POS/backend/alembic.ini")
alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)


def _create_test_db_engine():
    return create_engine(TEST_DATABASE_URL, poolclass=NullPool)


def _reset_database(engine):
    """Drop all tables and alembic_version."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


def _run_migrations_up_to(target_revision: str):
    """Run alembic migrations up to target_revision."""
    command.upgrade(alembic_cfg, target_revision)


def _get_current_revision(engine):
    with engine.begin() as conn:
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        row = result.fetchone()
        return row[0] if row else None


class TestMigration0036EdgeCases:
    """Test migration 0036 handling of legacy edge cases."""

    def setup_method(self):
        self.engine = _create_test_db_engine()
        _reset_database(self.engine)
        # Run migrations up to 0035 (before 0036)
        _run_migrations_up_to("0035_import_mapping_persistence")

    def teardown_method(self):
        self.engine.dispose()

    def _insert_legacy_batch(
        self,
        session: Session,
        *,
        batch_id: uuid.UUID = None,
        branch_id: uuid.UUID = None,
        filename: str = "legacy.csv",
        uploaded_by: uuid.UUID = None,
        status: str = "PENDING_APPROVAL",
        rows: list[dict] = None,
    ) -> uuid.UUID:
        """Insert a legacy import_batch with optional staging rows."""
        batch_id = batch_id or uuid.uuid4()
        branch_id = branch_id or uuid.uuid4()
        uploaded_by = uploaded_by or uuid.uuid4()

        # Insert supporting rows to satisfy foreign keys
        session.execute(
            text("""
                INSERT INTO branches (id, code, name, created_at, updated_at)
                VALUES (:id, :code, :name, :created_at, :updated_at)
                ON CONFLICT (id) DO NOTHING
            """),
            {
                "id": branch_id,
                "code": "TEST",
                "name": "Test Branch",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )
        # Insert a role for the user FK
        role_id = uuid.uuid4()
        session.execute(
            text("""
                INSERT INTO roles (id, code, name, is_system, created_at, updated_at)
                VALUES (:id, :code, :name, :is_system, :created_at, :updated_at)
                ON CONFLICT (id) DO NOTHING
            """),
            {
                "id": role_id,
                "code": "admin",
                "name": "Administrator",
                "is_system": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )
        session.execute(
            text("""
                INSERT INTO users (id, username, password_hash, display_name, role_id, branch_id, is_active, must_change_password, failed_login_count, version, created_at, updated_at)
                VALUES (:id, :username, :password_hash, :display_name, :role_id, :branch_id, :is_active, :must_change_password, :failed_login_count, :version, :created_at, :updated_at)
                ON CONFLICT (id) DO NOTHING
            """),
            {
                "id": uploaded_by,
                "username": "test_user",
                "password_hash": "test",
                "display_name": "Test User",
                "role_id": role_id,
                "branch_id": branch_id,
                "is_active": True,
                "must_change_password": False,
                "failed_login_count": 0,
                "version": 1,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )

        session.execute(
            text("""
                INSERT INTO import_batches (id, branch_id, filename, uploaded_by, uploaded_at, status, created_at, updated_at)
                VALUES (:id, :branch_id, :filename, :uploaded_by, :uploaded_at, :status, :created_at, :updated_at)
            """),
            {
                "id": batch_id,
                "branch_id": branch_id,
                "filename": filename,
                "uploaded_by": uploaded_by,
                "uploaded_at": datetime.now(timezone.utc),
                "status": status,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
},
        )

        if rows:
            for idx, row_data in enumerate(rows):
                row_id = uuid.uuid4()
                session.execute(
                    text("""
                        INSERT INTO import_staging_rows (id, batch_id, row_number, row_type, raw_data, validation_status, created_at, updated_at)
                        VALUES (:id, :batch_id, :row_number, :row_type, :raw_data, :validation_status, :created_at, :updated_at)
                    """),
                    {
                        "id": row_id,
                        "batch_id": batch_id,
                        "row_number": idx + 2,
                        "row_type": row_data["row_type"],
                        "raw_data": json.dumps(row_data["raw_data"]),
                        "validation_status": row_data.get("validation_status", "PENDING"),
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    },
                )

        session.commit()
        return batch_id

    def test_empty_batch_raises_explicit_error(self):
        """Migration should fail explicitly for batches with no staging rows."""
        with Session(self.engine) as session:
            self._insert_legacy_batch(session, rows=[])

        with pytest.raises(Exception) as exc_info:
            _run_migrations_up_to("0036_import_batch_idempotency")

        assert "empty" in str(exc_info.value).lower() or "no staging rows" in str(exc_info.value).lower()

    def test_mixed_row_types_raises_explicit_error(self):
        """Migration should fail explicitly for batches with mixed row types."""
        with Session(self.engine) as session:
            self._insert_legacy_batch(
                session,
                rows=[
                    {"row_type": "ITEM", "raw_data": {"ITEM CODE": "LVT001"}},
                    {"row_type": "PURCHASE", "raw_data": {"DATE": "2024-01-01"}},
                    {"row_type": "ITEM", "raw_data": {"ITEM CODE": "LVT002"}},
                ],
            )

        with pytest.raises(Exception) as exc_info:
            _run_migrations_up_to("0036_import_batch_idempotency")

        assert "mixed" in str(exc_info.value).lower() or "multiple row types" in str(exc_info.value).lower()

    def test_single_type_batch_migrates_successfully(self):
        """Batches with consistent row types should migrate successfully."""
        with Session(self.engine) as session:
            batch_id = self._insert_legacy_batch(
                session,
                rows=[
                    {"row_type": "ITEM", "raw_data": {"ITEM CODE": "LVT001"}},
                    {"row_type": "ITEM", "raw_data": {"ITEM CODE": "LVT002"}},
                ],
            )

        _run_migrations_up_to("0036_import_batch_idempotency")

        with Session(self.engine) as session:
            result = session.execute(
                text("SELECT import_type FROM import_batches WHERE id = :id"),
                {"id": batch_id},
            ).fetchone()
            assert result[0] == "ITEM"

    def test_all_import_types_migrate_correctly(self):
        """Each supported import type should migrate to correct import_type."""
        for import_type in ["ITEM", "PURCHASE", "SALE"]:
            _reset_database(self.engine)
            _run_migrations_up_to("0035_import_mapping_persistence")

            with Session(self.engine) as session:
                self._insert_legacy_batch(
                    session,
                    rows=[
                        {"row_type": import_type, "raw_data": {"test": "data"}},
                    ],
                )

            _run_migrations_up_to("0036_import_batch_idempotency")

            with Session(self.engine) as session:
                result = session.execute(
                    text("SELECT import_type FROM import_batches"),
                ).fetchone()
                assert result[0] == import_type

    def test_downgrade_restores_pre_migration_state(self):
        """Downgrade should remove added columns cleanly."""
        with Session(self.engine) as session:
            self._insert_legacy_batch(
                session,
                rows=[{"row_type": "ITEM", "raw_data": {"ITEM CODE": "LVT001"}}],
            )

        _run_migrations_up_to("0036_import_batch_idempotency")
        command.downgrade(alembic_cfg, "0035_import_mapping_persistence")

        with Session(self.engine) as session:
            cols = session.execute(
                text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'import_batches'
                    AND column_name IN ('import_type', 'content_hash')
                """)
            ).fetchall()
            assert len(cols) == 0

            constraints = session.execute(
                text("""
                    SELECT constraint_name FROM information_schema.table_constraints
                    WHERE table_name = 'import_batches'
                    AND constraint_name = 'uq_import_batch_dedupe'
                """)
            ).fetchall()
            assert len(constraints) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


