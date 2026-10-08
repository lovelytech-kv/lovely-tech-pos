param(
    [int]$DatabaseReadyAttempts = 12,
    [int]$DatabaseRetrySeconds = 5,
    [int]$Port = 8000,
    [string]$EnvFile = ".env"
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $ProjectRoot
$python = "$ProjectRoot\backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "backend/.venv missing. Run Install-LovelyTechServer.ps1 first." }
$env:PYTHONPATH = "$ProjectRoot\backend"
# Staging uses a separate env file (e.g. .env.staging) so it can never touch the production database.
$env:LTPOS_ENV_FILE = $EnvFile

Push-Location "$ProjectRoot\backend"
try {
    $ready = $false
    for ($i = 1; $i -le $DatabaseReadyAttempts; $i++) {
        & $python -c "from app.db.session import get_engine; get_engine().connect().close(); print('DB_READY')"
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        if ($i -lt $DatabaseReadyAttempts) { Start-Sleep -Seconds $DatabaseRetrySeconds }
    }
    if (-not $ready) { throw "PostgreSQL was not ready after $DatabaseReadyAttempts attempts." }

    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Alembic migration failed." }

    & $python -m uvicorn app.main:app --host 0.0.0.0 --port $Port
    if ($LASTEXITCODE -ne 0) { throw "Lovely Tech POS server stopped with exit code $LASTEXITCODE." }
}
finally {
    Pop-Location
}
