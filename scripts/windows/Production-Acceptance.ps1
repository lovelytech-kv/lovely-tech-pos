param(
    [Parameter(Mandatory=$true)][string]$ServerUrl,
    [switch]$SkipBackendTests,
    [switch]$SkipFrontendBuild
)
$ErrorActionPreference = "Stop"

function Invoke-JsonGet([string]$Url) {
    return Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 10
}

try { $uri = [Uri]$ServerUrl } catch { throw "ServerUrl must be an absolute URL." }
if (-not $uri.IsAbsoluteUri -or [string]::IsNullOrWhiteSpace($uri.Host)) { throw "ServerUrl must be an absolute URL." }
if ($uri.Scheme -notin @("http", "https")) { throw "ServerUrl must use http or https." }

$health = Invoke-JsonGet "$($uri.AbsoluteUri.TrimEnd('/'))/health"
if ($health.status -ne "ok") { throw "API health check failed." }
$ready = Invoke-JsonGet "$($uri.AbsoluteUri.TrimEnd('/'))/health/readiness"
if ($ready.status -ne "ready" -or $ready.database -ne "ok") { throw "API/database readiness check failed." }

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

if (-not $SkipBackendTests) {
    $python = Join-Path $root "backend\.venv\Scripts\python.exe"
    if (-not (Test-Path $python)) { throw "backend/.venv is missing; run Install-LovelyTechServer.ps1 first." }
    Push-Location $root
    try {
        & $python -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw "Backend acceptance tests failed." }
    } finally { Pop-Location }
}

if (-not $SkipFrontendBuild) {
    $frontend = Join-Path $root "frontend"
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "npm was not found." }
    Push-Location $frontend
    try {
        if (Test-Path "package-lock.json") { npm ci } else { npm install }
        if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend production build failed." }
    } finally { Pop-Location }
}

Write-Host "Lovely Tech POS production acceptance: PASS"
Write-Host "Server: $ServerUrl"
Write-Host "API: healthy"
Write-Host "Database: ready"
if (-not $SkipBackendTests) { Write-Host "Backend tests: PASS" }
if (-not $SkipFrontendBuild) { Write-Host "Frontend build: PASS" }
