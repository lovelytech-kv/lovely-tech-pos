$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $ProjectRoot
$pyVersion = (python --version 2>&1).ToString()
if ($pyVersion -notmatch "Python 3\.13\.") { throw "Python 3.13 is required. Found: $pyVersion" }
Push-Location "$ProjectRoot\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[test]"
Pop-Location
Write-Host "Backend environment installed. Configure backend/.env before starting the server."
