from app.core.config import Settings, validate_production_settings


def test_production_rejects_default_secret(monkeypatch):
    import app.core.config as config
    old = config.settings
    config.settings = Settings(app_env='production', secret_key='development-only-change-me', database_url='postgresql+psycopg://u:strong@host/db')
    try:
        try:
            validate_production_settings()
        except RuntimeError as exc:
            assert 'SECRET_KEY' in str(exc)
        else:
            raise AssertionError('expected production secret validation failure')
    finally:
        config.settings = old


def test_cors_origins_are_explicit():
    import app.core.config as config
    assert '*' not in config.settings.cors_origins
    assert 'http://localhost:5173' in config.settings.cors_origins


def _prod(secret, db='postgresql+psycopg://u:strong@host/db'):
    import app.core.config as config
    old = config.settings
    config.settings = Settings(app_env='production', secret_key=secret, database_url=db)
    try:
        config.validate_production_settings()
    finally:
        config.settings = old


def test_production_rejects_example_placeholders_and_short_secret():
    import pytest
    with pytest.raises(RuntimeError):
        _prod('CHANGE_ME_TO_A_LONG_RANDOM_SECRET_AT_LEAST_32_CHARS')
    with pytest.raises(RuntimeError):
        _prod('short-secret')
    with pytest.raises(RuntimeError):
        _prod('x' * 40, 'postgresql+psycopg://lovely_pos:CHANGE_ME_DB_PASSWORD@127.0.0.1:5432/db')
    _prod('x' * 40)
