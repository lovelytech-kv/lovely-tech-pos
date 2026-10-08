param([string]$BaseUrl="http://127.0.0.1:8000")
$ErrorActionPreference = "Stop"
$health=Invoke-RestMethod "$BaseUrl/health"
if ($health.status -ne "ok") { throw "Health check failed." }
try { $ready=Invoke-RestMethod "$BaseUrl/health/readiness"; if ($ready.status -ne "ready") { throw "Readiness failed." } }
catch { throw "Database readiness failed: $($_.Exception.Message)" }
Write-Host "Lovely Tech POS server is healthy and database-ready."
