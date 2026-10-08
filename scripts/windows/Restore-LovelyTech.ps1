param([Parameter(Mandatory=$true)][string]$Backup,[string]$DatabaseUrl=$env:DATABASE_URL,[string]$Secret=$env:SECRET_KEY)
$ErrorActionPreference = "Stop"
if (-not $DatabaseUrl) { throw "DATABASE_URL is required." }
if (-not $Secret) { throw "SECRET_KEY is required." }
$root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH="$root\backend"
$env:SECRET_KEY=$Secret
$safety=Join-Path $root ("backups\pre-restore-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".ltbak")
Push-Location "$root\backend"
& .\.venv\Scripts\python.exe "$root\scripts\postgres_restore_runner.py" --database-url $DatabaseUrl --backup $Backup --safety-output $safety --confirm
Pop-Location
