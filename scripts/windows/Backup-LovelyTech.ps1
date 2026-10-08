param([string]$DatabaseUrl=$env:DATABASE_URL,[string]$Secret=$env:SECRET_KEY,[string]$Output=(Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) "backups"))
$ErrorActionPreference = "Stop"
if (-not $DatabaseUrl) { throw "DATABASE_URL is required." }
if (-not $Secret) { throw "SECRET_KEY is required." }
$root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH="$root\backend"
$env:SECRET_KEY=$Secret
New-Item -ItemType Directory -Force -Path $Output | Out-Null
$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
Push-Location "$root\backend"
& .\.venv\Scripts\python.exe "$root\scripts\postgres_backup_runner.py" --database-url $DatabaseUrl --output (Join-Path $Output "lovely-tech-$stamp.ltbak")
Pop-Location
