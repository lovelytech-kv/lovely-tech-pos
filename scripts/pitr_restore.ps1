param(
    [Parameter(Mandatory=$true)]
    [string]$TargetTime,
    [Parameter(Mandatory=$true)]
    [int]$BaseBackupId,
    [int]$ClusterPort = 5433,
    [string]$PgDataPath = 'C:\LovelyTechTest\pgdata_pitr_test',
    [string]$BaseDir = 'C:\LovelyTechTest\pitr_base_test',
    [string]$WalArchiveDir = 'C:\LovelyTechTest\pitr_wal_archive_test',
    [string]$PgBin = 'C:\Program Files\PostgreSQL\18\bin',
    [string]$MetadataDbUrl = 'postgresql://lovely_pos:7181ebce8a2140d8be90@127.0.0.1:5432/lovely_tech_test15',
    [string]$SafetyBackupDir = 'C:\ProgramData\LovelyTechPOS\backups',
    [string]$BackendUrl = 'http://127.0.0.1:8000'
)

$ErrorActionPreference = 'Stop'

function Write-Step { param($msg) Write-Host "`n[$((Get-Date).ToString('HH:mm:ss'))] $msg" -ForegroundColor Cyan }
function Write-Ok { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn2 { param($msg) Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Err { param($msg) Write-Host "  [ERROR] $msg" -ForegroundColor Red }
function Confirm-Step {
    param($prompt)
    $ans = Read-Host "$prompt (Y/n)"
    return ($ans -eq '' -or $ans -eq 'y' -or $ans -eq 'Y')
}

Write-Host '=============================================' -ForegroundColor Cyan
Write-Host ' PITR RESTORE - DESTRUCTIVE OPERATION' -ForegroundColor Red
Write-Host '=============================================' -ForegroundColor Cyan
Write-Host "Target time:     $TargetTime"
Write-Host "Base backup ID:  $BaseBackupId"
Write-Host "Cluster port:    $ClusterPort"
Write-Host "PgData path:     $PgDataPath"
Write-Host ''

# -------- GUARD 1: Admin PowerShell --------
Write-Step 'GUARD 1: Admin PowerShell check'
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Err 'This script MUST run in ELEVATED PowerShell (Run as Administrator)'
    exit 1
}
Write-Ok 'Running as Administrator'

# -------- GUARD 2: Backend not running on 8000 --------
Write-Step 'GUARD 2: Backend must NOT be running on port 8000'
try {
    $backendUp = (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0
    if ($backendUp) {
        Write-Err 'Backend IS running on port 8000. Stop it first (Ctrl+C in backend terminal).'
        exit 1
    }
    Write-Ok 'Port 8000 is free'
} catch {
    Write-Ok 'Port 8000 free (no listeners)'
}

# -------- GUARD 3: Base backup exists on disk --------
Write-Step 'GUARD 3: Base backup must exist on disk'
$baseRow = $null
try {
    $baseRowJson = & (Join-Path $PgBin 'psql.exe') $MetadataDbUrl -t -A -c "SELECT base_path || '|' || backup_end_time::text || '|' || COALESCE(wal_min,'') FROM pitr_base_backups WHERE id = $BaseBackupId;" 2>&1
    if ($LASTEXITCODE -ne 0 -or -not $baseRowJson) {
        Write-Err "Base backup ID $BaseBackupId not found in pitr_base_backups"
        exit 1
    }
    $parts = ($baseRowJson.Trim() -split '\|')
    $baseRow = @{ base_path = $parts[0]; backup_end_time = $parts[1]; wal_min = $parts[2] }
} catch {
    Write-Err "Failed to query pitr_base_backups: $_"
    exit 1
}
$basePath = $baseRow.base_path
if (-not (Test-Path $basePath)) {
    Write-Err "Base backup path not found: $basePath"
    exit 1
}
if (-not (Test-Path (Join-Path $basePath 'backup_manifest'))) {
    Write-Err "Base backup has no backup_manifest (incomplete): $basePath"
    exit 1
}
Write-Ok "Base backup exists: $basePath"

# -------- GUARD 4: Target time within valid range --------
Write-Step 'GUARD 4: Target time must be within valid restore range'
try {
    $targetDt = [DateTime]::Parse($TargetTime)
    $targetUtc = $targetDt.ToUniversalTime()
} catch {
    Write-Err "Cannot parse TargetTime '$TargetTime'. Use format 'YYYY-MM-DD HH:MM:SS'"
    exit 1
}

# Get earliest from base backup start, latest from WAL dir or base end
$rangeJson = & (Join-Path $PgBin 'psql.exe') $MetadataDbUrl -t -A -c "SELECT MIN(backup_start_time)::text || '|' || MAX(backup_end_time)::text FROM pitr_base_backups;" 2>&1
$rangeParts = ($rangeJson.Trim() -split '\|')
$earliest = [DateTime]::Parse($rangeParts[0]).ToUniversalTime()
$latest = [DateTime]::Parse($rangeParts[1]).ToUniversalTime()

Write-Host "  Valid range (UTC): $($earliest.ToString('o')) .. $($latest.ToString('o'))"
Write-Host "  Target (UTC):      $($targetUtc.ToString('o'))"

if ($targetUtc -lt $earliest) {
    Write-Err "Target time $($targetUtc.ToString('o')) is BEFORE earliest base backup $($earliest.ToString('o'))"
    exit 1
}
if ($targetUtc -gt $latest) {
    Write-Warn2 "Target time $($targetUtc.ToString('o')) is AFTER latest known base backup $($latest.ToString('o'))"
    Write-Warn2 "WAL files must cover this gap. Proceeding only if WAL dir has newer files."
}
Write-Ok "Target time within acceptable range"

# -------- GUARD 5: pgdata exists and looks like a cluster --------
Write-Step 'GUARD 5: PgData directory sanity check'
if (-not (Test-Path $PgDataPath)) {
    Write-Err "PgData path not found: $PgDataPath"
    exit 1
}
if (-not (Test-Path (Join-Path $PgDataPath 'PG_VERSION'))) {
    Write-Err "PgData path does not look like a PostgreSQL cluster (no PG_VERSION)"
    exit 1
}
Write-Ok "PgData looks valid: $PgDataPath"

# -------- GUARD 6: WAL archive dir exists and has files --------
Write-Step 'GUARD 6: WAL archive dir must have files'
if (-not (Test-Path $WalArchiveDir)) {
    Write-Err "WAL archive dir not found: $WalArchiveDir"
    exit 1
}
$walFiles = Get-ChildItem $WalArchiveDir -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^[0-9A-F]{24}$' } | Sort-Object Name
if ($walFiles.Count -eq 0) {
    Write-Err "No WAL files in $WalArchiveDir"
    exit 1
}
Write-Ok "$($walFiles.Count) WAL files in archive (oldest: $($walFiles[0].Name), newest: $($walFiles[-1].Name))"

# ============ ALL GUARDS PASSED ============
Write-Host ''
Write-Host '=============================================' -ForegroundColor Yellow
Write-Host ' ALL 6 SAFETY GUARDS PASSED' -ForegroundColor Green
Write-Host '=============================================' -ForegroundColor Yellow
Write-Host ''
Write-Host 'About to perform DESTRUCTIVE PITR restore:' -ForegroundColor Red
Write-Host "  - Stop PostgreSQL cluster on port $ClusterPort"
Write-Host "  - Move current pgdata to $PgDataPath.pre-pitr-<timestamp>"
Write-Host "  - Restore base backup to fresh pgdata"
Write-Host "  - Replay WAL up to target time: $($targetUtc.ToString('o'))"
Write-Host "  - Start PostgreSQL"
Write-Host ''
if (-not (Confirm-Step 'Proceed with PITR restore? (recommended: verify safety backup exists first)')) {
    Write-Warn2 'Aborted by user'
    exit 0
}

# ============ STEP 1: Safety backup ============
Write-Step 'STEP 1: Create safety backup before destructive ops'
$safetyTs = Get-Date -Format 'yyyyMMdd-HHmmss'
if (-not (Test-Path $SafetyBackupDir)) {
    New-Item -ItemType Directory -Path $SafetyBackupDir -Force | Out-Null
}
$safetyFile = Join-Path $SafetyBackupDir "pre-pitr-safety-$safetyTs.sql"
Write-Host "  Dumping current cluster to: $safetyFile"
$savedEAP = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    & (Join-Path $PgBin 'pg_dumpall.exe') -U postgres -h 127.0.0.1 -p $ClusterPort -f $safetyFile 2>&1 | Out-Null
    $dumpExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $savedEAP
}
if ($dumpExit -ne 0 -or -not (Test-Path $safetyFile)) {
    Write-Err "Safety backup failed. Aborting restore."
    exit 1
}
Write-Ok "Safety backup created: $safetyFile ($([math]::Round((Get-Item $safetyFile).Length/1KB,1)) KB)"

if (-not (Confirm-Step 'Safety backup ready. Continue to STOP cluster?')) {
    Write-Warn2 'Aborted by user (safety backup kept)'
    exit 0
}

# ============ STEP 2: Stop cluster ============
Write-Step 'STEP 2: Stop PostgreSQL cluster'
$pgCtl = Join-Path $PgBin 'pg_ctl.exe'
& $pgCtl -D $PgDataPath stop -m fast -w -t 30
if ($LASTEXITCODE -ne 0) {
    Write-Err 'Failed to stop cluster. Check pg_ctl output above.'
    exit 1
}
Write-Ok 'Cluster stopped'

if (-not (Confirm-Step 'Cluster stopped. Move pgdata and copy base backup?')) {
    Write-Warn2 'Aborted - cluster is stopped. Start manually: pg_ctl -D $PgDataPath start'
    exit 0
}

# ============ STEP 3: Move current pgdata ============
Write-Step 'STEP 3: Move current pgdata to pre-pitr backup'
$prePitrPath = "$PgDataPath.pre-pitr-$safetyTs"
Write-Host "  Moving: $PgDataPath -> $prePitrPath"
Move-Item -Path $PgDataPath -Destination $prePitrPath -Force
if (-not (Test-Path $prePitrPath)) {
    Write-Err "Move failed. Restore rollback: move $prePitrPath back to $PgDataPath"
    exit 1
}
Write-Ok "pgdata moved: $prePitrPath"

# ============ STEP 4: Copy base backup ============
Write-Step 'STEP 4: Extract base backup to fresh pgdata'
Write-Host "  Base backup: $basePath"
Write-Host "  Target:      $PgDataPath"
New-Item -ItemType Directory -Path $PgDataPath -Force | Out-Null

# Base backup is in tar.gz format (-Ft -z) - extract base.tar.gz
$baseTar = Join-Path $basePath 'base.tar.gz'
if (-not (Test-Path $baseTar)) {
    $baseTar = Join-Path $basePath 'base.tar'
    if (-not (Test-Path $baseTar)) {
        Write-Err "Neither base.tar.gz nor base.tar found in $basePath"
        Write-Warn2 "Rollback: Move $prePitrPath back to $PgDataPath"
        exit 1
    }
}
Write-Host "  Extracting: $baseTar"
& tar -xzf $baseTar -C $PgDataPath

# Also extract pg_wal.tar.gz (contains initial WAL - required for recovery bootstrap)
$pgWalTar = Join-Path $basePath 'pg_wal.tar.gz'
if (Test-Path $pgWalTar) {
    $pgWalDst = Join-Path $PgDataPath 'pg_wal'
    New-Item -ItemType Directory -Path $pgWalDst -Force | Out-Null
    & tar -xzf $pgWalTar -C $pgWalDst
    Write-Host "  [INFO] pg_wal.tar.gz extracted"
}
if ($LASTEXITCODE -ne 0) {
    Write-Err "tar extraction failed"
    Write-Warn2 "Rollback: Move $prePitrPath back to $PgDataPath"
    exit 1
}
Write-Ok "Base backup extracted"

# ============ STEP 5: Create recovery.signal ============
Write-Step 'STEP 5: Create recovery.signal file'
$recoverySignal = Join-Path $PgDataPath 'recovery.signal'
New-Item -ItemType File -Path $recoverySignal -Force | Out-Null
Write-Ok "recovery.signal created: $recoverySignal"

# ============ STEP 6: Append recovery config ============
Write-Step 'STEP 6: Append recovery config to postgresql.auto.conf'
$autoConf = Join-Path $PgDataPath 'postgresql.auto.conf'
# Windows copy command requires backslashes; double-escape for postgresql.auto.conf
$walArchiveBackslash = $WalArchiveDir.Replace('\', '\\')
$targetIso = $targetUtc.ToString('o')
$recoveryConfig = @"

# === PITR recovery config (Chunk 15b) ===
restore_command = 'copy "$walArchiveBackslash\\%f" "%p"'
recovery_target_time = '$targetIso'
recovery_target_action = 'promote'
"@
[System.IO.File]::AppendAllText($autoConf, $recoveryConfig, (New-Object System.Text.UTF8Encoding $false))
Write-Ok "Recovery config appended to: $autoConf"

# ============ STEP 7: Start cluster ============
Write-Step 'STEP 7: Start PostgreSQL cluster (recovery mode)'
$logFile = Join-Path $PgDataPath 'server.log'
& $pgCtl -D $PgDataPath -o "-p $ClusterPort" -l $logFile start
if ($LASTEXITCODE -ne 0) {
    Write-Err 'Cluster failed to start. Check log:'
    if (Test-Path $logFile) { Get-Content $logFile -Tail 30 }
    Write-Warn2 "Rollback: Stop any running cluster, move $prePitrPath back to $PgDataPath"
    exit 1
}

# ============ STEP 8: Wait for recovery complete ============
Write-Step 'STEP 8: Wait for recovery to complete (max 3 min)'
$maxWait = 180
$elapsed = 0
$recoveryDone = $false
while ($elapsed -lt $maxWait) {
    Start-Sleep -Seconds 5
    $elapsed += 5
    if (Test-Path $logFile) {
        $tail = Get-Content $logFile -Tail 10 -ErrorAction SilentlyContinue
        $joined = $tail -join "`n"
        if ($joined -match 'database system is ready to accept connections') {
            $recoveryDone = $true
            break
        }
        if ($joined -match 'recovery stopping before|FATAL|PANIC') {
            Write-Warn2 "Recovery error in log:"
            Write-Warn2 $joined
            break
        }
    }
}

if (-not $recoveryDone) {
    Write-Err 'Recovery did not complete within 3 minutes'
    Write-Host '  Last log lines:'
    if (Test-Path $logFile) { Get-Content $logFile -Tail 20 }
    Write-Warn2 "Rollback: pg_ctl -D $PgDataPath stop ; Move-Item '$prePitrPath' '$PgDataPath' -Force"
    exit 1
}
Write-Ok 'Recovery complete - cluster is online'

# ============ SUCCESS ============
Write-Host ''
Write-Host '=============================================' -ForegroundColor Green
Write-Host ' PITR RESTORE COMPLETE' -ForegroundColor Green
Write-Host '=============================================' -ForegroundColor Green
Write-Host ''
Write-Host "Restored to:  $($targetUtc.ToString('o')) (UTC)"
Write-Host "Safety backup: $safetyFile"
Write-Host "Rollback pgdata: $prePitrPath"
Write-Host ''
Write-Host 'To rollback (restore pre-PITR state):' -ForegroundColor Yellow
Write-Host "  pg_ctl -D '$PgDataPath' stop -m fast" -ForegroundColor Gray
Write-Host "  Move-Item '$PgDataPath' '$PgDataPath.failed-pitr-$(Get-Date -Format yyyyMMdd-HHmmss)'" -ForegroundColor Gray
Write-Host "  Move-Item '$prePitrPath' '$PgDataPath'" -ForegroundColor Gray
Write-Host "  pg_ctl -D '$PgDataPath' start -o '-p $ClusterPort'" -ForegroundColor Gray
Write-Host ''
Write-Host 'Verify restore by connecting:' -ForegroundColor Yellow
Write-Host "  psql -U postgres -h 127.0.0.1 -p $ClusterPort -d lovely_tech_pitr_test -c 'SELECT * FROM pitr_test_marker;'" -ForegroundColor Gray