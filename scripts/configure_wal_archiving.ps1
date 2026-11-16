param(
    [string]$PgDataPath = 'C:\Program Files\PostgreSQL\18\data',
    [int]$ClusterPort = 5432,
    [string]$ArchiveDir = 'C:\ProgramData\LovelyTechPOS\wal_archive',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
Write-Host '=== WAL Archiving Configuration ===' -ForegroundColor Cyan
Write-Host "PgDataPath:  $PgDataPath"
Write-Host "ClusterPort: $ClusterPort"
Write-Host "ArchiveDir:  $ArchiveDir"
Write-Host ''

$confPath = Join-Path $PgDataPath 'postgresql.conf'
if (-not (Test-Path $confPath)) {
    Write-Host "[ERROR] postgresql.conf not found at $confPath" -ForegroundColor Red
    exit 1
}
Write-Host '[OK] postgresql.conf found' -ForegroundColor Green

$existing = Get-Content $confPath -Raw
$alreadyConfigured = ($existing -match '(?m)^\s*archive_mode\s*=\s*on\b')
if ($alreadyConfigured -and -not $Force) {
    Write-Host '[WARN] WAL archiving already configured (archive_mode = on)' -ForegroundColor Yellow
    $response = Read-Host 'Re-configure (overwrite postgresql.conf)? (y/N)'
    if ($response -ne 'y' -and $response -ne 'Y') {
        Write-Host 'Aborted - no changes made.' -ForegroundColor Yellow
        exit 0
    }
}

if (-not (Test-Path $ArchiveDir)) {
    New-Item -ItemType Directory -Path $ArchiveDir -Force | Out-Null
    Write-Host "[OK] Created archive dir: $ArchiveDir" -ForegroundColor Green
} else {
    Write-Host "[OK] Archive dir exists: $ArchiveDir" -ForegroundColor Green
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupPath = "$confPath.bak.$timestamp"
Copy-Item $confPath $backupPath -Force
if (-not (Test-Path $backupPath)) {
    Write-Host "[ERROR] Failed to create backup at $backupPath" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Backup created: $backupPath" -ForegroundColor Green

# PostgreSQL GUC parser strips unescaped backslashes from string values.
# Forward slashes are PostgreSQL-native on Windows and avoid escape issues.
$archiveCommandForward = $ArchiveDir.Replace('\', '/')
$archiveCommandValue = 'copy "%p" "' + $archiveCommandForward + '/%f"'

$configBlock = @"

# === Lovely Tech POS - WAL Archiving (Chunk 15b, $timestamp) ===
# Previous config backed up to: $backupPath
wal_level = replica
archive_mode = on
archive_command = '$archiveCommandValue'
archive_timeout = 300
wal_keep_size = 512MB
max_wal_senders = 3
# === END Lovely Tech POS WAL Archiving ===

"@

[System.IO.File]::AppendAllText($confPath, $configBlock, (New-Object System.Text.UTF8Encoding $false))
Write-Host '[OK] Appended WAL config to postgresql.conf' -ForegroundColor Green

$after = Get-Content $confPath -Raw
if ($after -notmatch '(?m)^\s*archive_mode\s*=\s*on\b') {
    Write-Host '[ERROR] Verification failed: archive_mode = on not found after append' -ForegroundColor Red
    exit 1
}
Write-Host '[OK] Verified archive_mode = on' -ForegroundColor Green

Write-Host ''
Write-Host '=== NEXT STEPS ===' -ForegroundColor Cyan
Write-Host '1. RESTART PostgreSQL (this script does NOT restart it):' -ForegroundColor Yellow
Write-Host '   Production cluster (Windows service):' -ForegroundColor White
Write-Host '     Restart-Service postgresql-x64-18' -ForegroundColor Gray
Write-Host '   Test cluster (pg_ctl):' -ForegroundColor White
Write-Host "     & 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe' -D '$PgDataPath' -o '-p $ClusterPort' restart" -ForegroundColor Gray
Write-Host ''
Write-Host "2. Verify WAL files appear in: $ArchiveDir" -ForegroundColor Yellow
Write-Host ''
Write-Host '3. Create first base backup:' -ForegroundColor Yellow
Write-Host "     .\scripts\pitr_base_backup.ps1 -ClusterPort $ClusterPort" -ForegroundColor Gray
Write-Host ''
Write-Host 'Done.' -ForegroundColor Green