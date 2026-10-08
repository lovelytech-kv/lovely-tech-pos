from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_declares_build_backend_and_only_packages_app():
    text = (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    assert "[build-system]" in text
    assert 'include = ["app*"]' in text  # otherwise "pip install -e ." fails: app + alembic both discovered


def test_alembic_dir_does_not_shadow_alembic_library():
    assert not (ROOT / "backend" / "alembic" / "__init__.py").exists()


def test_start_script_uses_existing_engine_factory():
    text = (ROOT / "scripts" / "windows" / "Start-LovelyTechServer.ps1").read_text(encoding="utf-8")
    assert "get_engine()" in text
    assert "import engine" not in text


def test_libpq_url_strips_sqlalchemy_driver():
    from app.backup.service import libpq_url
    assert libpq_url("postgresql+psycopg://u:p@h:5432/d") == "postgresql://u:p@h:5432/d"
    assert libpq_url("postgresql://u:p@h/d") == "postgresql://u:p@h/d"


def test_backup_scripts_do_not_pass_secret_on_command_line():
    for name in ("Backup-LovelyTech.ps1", "Restore-LovelyTech.ps1"):
        assert "--secret" not in (ROOT / "scripts" / "windows" / name).read_text(encoding="utf-8")


def test_client_never_treats_non_json_200_as_success():
    text = (ROOT / "frontend" / "src" / "api" / "client.ts").read_text(encoding="utf-8")
    assert "JSON.parse(text)" in text and "non-JSON" in text
    assert "assertServerConfigured" in text
    assert "!result.access_token" in text  # login reply validated before saving session


def test_app_has_error_boundary_instead_of_blank_screen():
    text = (ROOT / "frontend" / "src" / "main.tsx").read_text(encoding="utf-8")
    assert "getDerivedStateFromError" in text and "<ErrorBoundary>" in text


def test_client_build_verifies_server_url_is_baked_in():
    text = (ROOT / "scripts" / "windows" / "Build-LovelyTechClient.ps1").read_text(encoding="utf-8")
    assert "NOT found in the built client" in text


def test_tauri_has_windows_icon_required_by_build():
    assert (ROOT / "desktop" / "tauri" / "icons" / "icon.ico").exists()
