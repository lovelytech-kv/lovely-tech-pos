param([string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
$ErrorActionPreference = "Stop"
if (-not (Test-Path $ProjectRoot)) { throw "Project root not found: $ProjectRoot" }
Write-Host "Protecting Lovely Tech POS server files: $ProjectRoot"
# The cashier must use only the POS client. Server source, .env, virtualenv and backups are admin/SYSTEM-only.
icacls $ProjectRoot /inheritance:r | Out-Null
icacls $ProjectRoot /grant:r "SYSTEM:(OI)(CI)(F)" "Administrators:(OI)(CI)(F)" | Out-Null
icacls $ProjectRoot /remove:g "Users" "Authenticated Users" "Everyone" 2>$null | Out-Null
if (Test-Path (Join-Path $ProjectRoot "backend\.env")) {
  icacls (Join-Path $ProjectRoot "backend\.env") /inheritance:r | Out-Null
  icacls (Join-Path $ProjectRoot "backend\.env") /grant:r "SYSTEM:(F)" "Administrators:(F)" | Out-Null
}
$backupRoot = Join-Path $ProjectRoot "backups"
New-Item -ItemType Directory -Force $backupRoot | Out-Null
icacls $backupRoot /inheritance:r | Out-Null
icacls $backupRoot /grant:r "SYSTEM:(OI)(CI)(F)" "Administrators:(OI)(CI)(F)" | Out-Null
icacls $backupRoot /remove:g "Users" "Authenticated Users" "Everyone" 2>$null | Out-Null
$serverDataRoot = "C:\ProgramData\LovelyTechPOS\server-data"
New-Item -ItemType Directory -Force $serverDataRoot | Out-Null
icacls $serverDataRoot /inheritance:r | Out-Null
icacls $serverDataRoot /grant:r "SYSTEM:(OI)(CI)(F)" "Administrators:(OI)(CI)(F)" | Out-Null
icacls $serverDataRoot /remove:g "Users" "Authenticated Users" "Everyone" 2>$null | Out-Null
Write-Host "Server files protected. Cashier Standard User must not have read/modify access to this folder."
