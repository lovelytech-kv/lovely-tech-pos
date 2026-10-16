from logging.config import fileConfig
from alembic import context
from sqlalchemy import inspect, text
from app.core.config import settings
from app.db.base import Base

config = context.config
if config.config_file_name and config.get_section("loggers"):
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
target_metadata = Base.metadata

# Alembic creates alembic_version.version_num as VARCHAR(32) before the first
# revision runs, which cannot hold revision IDs such as
# 0028_sale_return_exchange_version_lock (38 chars). Pre-create the table, or
# widen an existing column, to VARCHAR(64): Alembic reuses an existing table
# (create(checkfirst=True)) instead of creating its own VARCHAR(32) table, so
# fresh databases can execute every revision 0001 onward.
MIN_VERSION_NUM_LENGTH = 64


def _ensure_version_num_capacity(connection):
    inspector = inspect(connection)
    if not inspector.has_table("alembic_version"):
        connection.execute(text(
            "CREATE TABLE alembic_version ("
            "version_num VARCHAR(64) NOT NULL, "
            "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        ))
        return
    for column in inspector.get_columns("alembic_version"):
        if column["name"] == "version_num":
            length = getattr(column["type"], "length", None)
            if length is not None and length < MIN_VERSION_NUM_LENGTH:
                connection.execute(text(
                    "ALTER TABLE alembic_version "
                    "ALTER COLUMN version_num TYPE VARCHAR(64)"
                ))
            return


def run_migrations_offline():
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    from sqlalchemy import engine_from_config, pool
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            _ensure_version_num_capacity(connection)
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
