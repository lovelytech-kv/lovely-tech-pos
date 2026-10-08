from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WINDOWS = ROOT / "scripts" / "windows"


def test_windows_server_start_retries_database_before_migrations():
    text = (WINDOWS / "Start-LovelyTechServer.ps1").read_text(encoding="utf-8")
    assert "DatabaseReadyAttempts" in text
    assert "Start-Sleep -Seconds $DatabaseRetrySeconds" in text
    assert "python -m alembic upgrade head" in text
    assert "uvicorn app.main:app --host 0.0.0.0 --port $Port" in text


def test_windows_server_preflight_checks_secrets_and_database():
    text = (WINDOWS / "Preflight-LovelyTechServer.ps1").read_text(encoding="utf-8")
    assert "Test-NetConnection" in text
    assert "DATABASE_URL" in text
    assert "SECRET_KEY" in text
    assert "Python 3.13" in text


def test_windows_server_boot_task_runs_as_system_with_retry():
    text = (WINDOWS / "Install-LovelyTechServerTask.ps1").read_text(encoding="utf-8")
    assert "New-ScheduledTaskTrigger -AtStartup" in text
    assert "-UserId \"SYSTEM\"" in text
    assert "-RestartCount 5" in text
