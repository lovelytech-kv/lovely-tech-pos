"""Real-PostgreSQL tests for alembic_version revision-ID capacity.

Alembic creates alembic_version.version_num as VARCHAR(32) before the
first revision runs, which cannot store revision IDs such as
0028_sale_return_exchange_version_lock. Verifies against the real
database that alembic_version exists, version_num can store at least
64 characters, the database remains stamped at
0030_audit_immutability, and no existing application data is changed.
The 64-character probe is written inside a transaction that is rolled
back, so no test rows persist.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.core.config import settings

BACKEND_DIR = Path(__file__).resolve().parent.parent
engine = create_engine(settings.database_url)

CAPACITY = 64
PROBE = "c" * CAPACITY


def _application_row_counts(conn):
    counts = {}
    for table in sorted(inspect(conn).get_table_names()):
        if table == "alembic_version":
            continue
        counts[table] = conn.execute(text(f'SELECT count(*) FROM "{table}"')).scalar()
    return counts


def test_alembic_version_capacity():
    with engine.connect() as conn:
        before = _application_row_counts(conn)

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            inspector = inspect(conn)

            # alembic_version exists and carries a version_num column
            assert inspector.has_table("alembic_version")
            columns = {
                column["name"]: column
                for column in inspector.get_columns("alembic_version")
            }
            assert "version_num" in columns

            # version_num can store at least 64 characters
            length = getattr(columns["version_num"]["type"], "length", None)
            assert length is None or length >= CAPACITY
            conn.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:v)"),
                {"v": PROBE},
            )
            assert (
                conn.execute(
                    text(
                        "SELECT version_num FROM alembic_version "
                        "WHERE version_num = :v"
                    ),
                    {"v": PROBE},
                ).scalar()
                == PROBE
            )

            # database remains stamped at the pre-existing head
            stamps = conn.execute(
                text(
                    "SELECT version_num FROM alembic_version "
                    "WHERE version_num <> :v ORDER BY version_num"
                ),
                {"v": PROBE},
            ).scalars().all()
            assert stamps == ["0035_import_mapping_persistence"]

            # no application data changed by the probe
            assert _application_row_counts(conn) == before
        finally:
            trans.rollback()

    with engine.connect() as conn:
        # nothing persisted: no probe row, no application data changed
        assert _application_row_counts(conn) == before
        assert conn.execute(
            text("SELECT count(*) FROM alembic_version WHERE version_num = :v"),
            {"v": PROBE},
        ).scalar() == 0


def test_version_capacity_migration_chain():
    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    assert head == "0036_import_batch_idempotency"
    revision = script.get_revision(head)
    assert revision.down_revision == "0035_import_mapping_persistence"
