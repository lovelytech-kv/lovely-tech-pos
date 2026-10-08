# Staging on the OWNER laptop: separate database + separate port, so production is never touched.
param(
    [string]$PgSuperUser = "postgres",
    [Parameter(Mandatory=$true)][string]$StagingDbPassword,
    [int]$Port = 8001
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$psql = "psql"
Write-Host "Creating staging role/database (you will be asked for the postgres superuser password)..."
& $psql -U $PgSuperUser -h 127.0.0.1 -c "DO `$`$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='lovely_staging') THEN CREATE ROLE lovely_staging LOGIN PASSWORD '$StagingDbPassword'; END IF; END `$`$;"
& $psql -U $PgSuperUser -h 127.0.0.1 -c "CREATE DATABASE lovely_tech_pos_staging OWNER lovely_staging;" 2>$null
$secret = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 48 | ForEach-Object {[char]$_})
$envPath = Join-Path $root "backend\.env.staging"
@"
APP_ENV=production
API_PORT=$Port
DATABASE_URL=postgresql+psycopg://lovely_staging:$StagingDbPassword@127.0.0.1:5432/lovely_tech_pos_staging
SECRET_KEY=$secret
CORS_ORIGINS=tauri://localhost,http://tauri.localhost,http://localhost:5173
BACKUP_ROOT=$root\staging-backups
REQUIRE_VERIFIED_BACKUP_FOR_CLOSE=true
APP_VERSION=0.4.0
PROTOCOL_VERSION=1.0.0
API_VERSION=1
BRANCH_CODE=STAGING
INSTANCE_ID_FILE=$root\staging-server-data\instance.json
"@ | Set-Content -Path $envPath -Encoding UTF8
Write-Host "Wrote $envPath (STAGING ONLY - uses fake data, never real shop data)."
Write-Host "Next: .\scripts\windows\Start-LovelyTechServer.ps1 -Port $Port -EnvFile .env.staging"
