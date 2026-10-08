param(
    [string]$DatabaseHost = "127.0.0.1",
    [int]$DatabasePort = 5432,
    [int]$ApiPort = 8000
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$python = "$ProjectRoot\backend\.venv\Scripts\python.exe"
$envFile = "$ProjectRoot\backend\.env"

$pythonVersion = (python --version 2>&1).ToString()
if ($pythonVersion -notmatch "Python 3\.13\.") { throw "Python 3.13 is required. Found: $pythonVersion" }
if (-not (Test-Path $python)) { throw "backend/.venv is missing." }
if (-not (Test-Path $envFile)) { throw "backend/.env is missing." }

$db = Test-NetConnection -ComputerName $DatabaseHost -Port $DatabasePort -WarningAction SilentlyContinue
if (-not $db.TcpTestSucceeded) { throw "PostgreSQL is not reachable at $DatabaseHost`:$DatabasePort." }

$apiListener = Get-NetTCPConnection -LocalPort $ApiPort -State Listen -ErrorAction SilentlyContinue
if ($apiListener) { Write-Warning "TCP $ApiPort is already listening. This is expected only when the POS server is already running." }

$envText = Get-Content $envFile -Raw
if ($envText -notmatch '(?m)^DATABASE_URL=.+') { throw "DATABASE_URL is missing from backend/.env." }
if ($envText -notmatch '(?m)^SECRET_KEY=.{32,}$') { throw "SECRET_KEY is missing or shorter than 32 characters." }

Write-Host "Lovely Tech POS server preflight: PASS"
Write-Host "Python: $pythonVersion"
Write-Host "PostgreSQL: reachable at $DatabaseHost`:$DatabasePort"
Write-Host "API port: $ApiPort"
