param(
    [int]$ClusterPort = 5432,
    [string]$PgUser = 'postgres',
    [string]$PgHost = '127.0.0.1',
    [string]$BaseDir = 'C:\ProgramData\LovelyTechPOS\pitr_base',
    [string]$WalArchiveDir = 'C:\ProgramData\LovelyTechPOS\wal_archive',
    [string]$PgBin = 'C:\Program Files\PostgreSQL\18\bin',
    [Parameter(Mandatory=$true)]
    [string]$MetadataDbUrl,
    [string]$CreatedBy = $env:USERNAME
)

$ErrorActionPreference = 'Stop'
Write-Host '=== PITR Base Backup ===' -ForegroundColor Cyan
Write-Host "Cluster:  $PgHost`:$ClusterPort"
Write-Host "BaseDir:  $BaseDir"
Write-Host "WALDir:   $WalArchiveDir"
Write-Host "MetadataDb: $MetadataDbUrl"
Write-Host ''

$pgBaseBackup = Join-Path $PgBin 'pg_basebackup.exe'
$psql = Join-Path $PgBin 'psql.exe'
if (-not (Test-Path $pgBaseBackup)) {
    Write-Host "[ERROR] pg_basebackup.exe not found at $pgBaseBackup" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $psql)) {
    Write-Host "[ERROR] psql.exe not found at $psql" -ForegroundColor Red
    exit 1
}
Write-Host '[OK] pg_basebackup.exe and psql.exe found' -ForegroundColor Green

if (-not (Test-Path $BaseDir)) {
    New-Item -ItemType Directory -Path $BaseDir -Force | Out-Null
    Write-Host "[OK] Created base dir: $BaseDir" -ForegroundColor Green
} else {
    Write-Host "[OK] Base dir exists: $BaseDir" -ForegroundColor Green
}

$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$basePath = Join-Path $BaseDir "base_$timestamp"
$startTime = [DateTime]::UtcNow
Write-Host "[INFO] Start time (UTC): $($startTime.ToString('o'))"

Get-ChildItem $BaseDir -Directory -Filter 'base_*' -ErrorAction SilentlyContinue | ForEach-Object {
    $hasManifest = Test-Path (Join-Path $_.FullName 'backup_manifest')
    if (-not $hasManifest) {
        $sz = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        Write-Host "[INFO] Removing partial base backup (no backup_manifest): $($_.Name) ($([math]::Round(($sz/1MB), 1)) MB)"
        Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "[INFO] Target path: $basePath"
Write-Host ''

Write-Host '[INFO] Running pg_basebackup (this may take 30-120s)...' -ForegroundColor Yellow
$backupArgs = @(
    '-D', $basePath,
    '-Ft', '-z',
    '-U', $PgUser,
    '-h', $PgHost,
    '-p', $ClusterPort
)
$savedEAP = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $proc = & $pgBaseBackup @backupArgs 2>&1
    $exitCode = $LASTEXITCODE
    $output = ($proc | ForEach-Object { "$_" }) -join "`n"
} finally {
    $ErrorActionPreference = $savedEAP
}
Write-Host $output
if ($exitCode -ne 0) {
    Write-Host "[ERROR] pg_basebackup failed (exit $exitCode)" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $basePath)) {
    Write-Host "[ERROR] Base backup directory not created: $basePath" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Base backup complete" -ForegroundColor Green

$endTime = [DateTime]::UtcNow
$sizeBytes = (Get-ChildItem $basePath -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Host "[INFO] End time (UTC): $($endTime.ToString('o'))"
Write-Host "[INFO] Size: $([math]::Round($sizeBytes / 1MB, 2)) MB ($sizeBytes bytes)"

$walMin = $null
$walMax = $null
if (Test-Path $WalArchiveDir) {
    $walFiles = Get-ChildItem $WalArchiveDir -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^[0-9A-F]{24}$' } | Sort-Object Name
    if ($walFiles.Count -gt 0) {
        $walMin = $walFiles[0].Name
        $walMax = $walFiles[$walFiles.Count - 1].Name
        Write-Host "[OK] WAL range: $walMin .. $walMax" -ForegroundColor Green
    } else {
        Write-Host '[WARN] No WAL files found in archive dir' -ForegroundColor Yellow
    }
} else {
    Write-Host "[WARN] WAL archive dir not found: $WalArchiveDir" -ForegroundColor Yellow
}

# Ensure pitr_base_backups table exists (idempotent - for throwaway clusters w/o migrations)
$createTableSql = @"
CREATE TABLE IF NOT EXISTS pitr_base_backups (
    id SERIAL PRIMARY KEY,
    base_path TEXT NOT NULL,
    backup_start_time TIMESTAMPTZ NOT NULL,
    backup_end_time TIMESTAMPTZ NOT NULL,
    wal_min TEXT,
    wal_max TEXT,
    size_bytes BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT
);
"@
$savedEAP3 = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $savedEAP3 = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    & $psql $MetadataDbUrl -c $createTableSql 2>&1 | Out-Null
} finally {
    $ErrorActionPreference = $savedEAP3
}
} finally {
    $ErrorActionPreference = $savedEAP3
}

$startIso = $startTime.ToString('o')
$endIso = $endTime.ToString('o')
$escapedPath = $basePath.Replace("'", "''")
$escapedUser = if ($CreatedBy) { $CreatedBy.Replace("'", "''") } else { 'unknown' }
$walMinSql = if ($walMin) { "'$walMin'" } else { 'NULL' }
$walMaxSql = if ($walMax) { "'$walMax'" } else { 'NULL' }

$insertSql = "INSERT INTO pitr_base_backups (base_path, backup_start_time, backup_end_time, wal_min, wal_max, size_bytes, created_by) VALUES ('$escapedPath', '$startIso', '$endIso', $walMinSql, $walMaxSql, $sizeBytes, '$escapedUser') RETURNING id;"
$insertOut = & $psql $MetadataDbUrl -t -A -c $insertSql 2>&1
$insertExit = $LASTEXITCODE

if ($insertExit -ne 0) {
    Write-Host "[ERROR] Failed to insert metadata: $insertOut" -ForegroundColor Red
    exit 1
}

$newId = ($insertOut -split "`n" | Where-Object { $_ -match '^\d+$' } | Select-Object -First 1)
Write-Host ''
Write-Host "[OK] Metadata inserted. Base backup ID = $newId" -ForegroundColor Green
Write-Host ''
Write-Host '=== SUMMARY ===' -ForegroundColor Cyan
Write-Host "Base backup ID:  $newId"
Write-Host "Path:            $basePath"
Write-Host "Start (UTC):     $startIso"
Write-Host "End (UTC):       $endIso"
Write-Host "Size:            $([math]::Round($sizeBytes / 1MB, 2)) MB"
Write-Host "WAL range:       $(if ($walMin) { "$walMin .. $walMax" } else { 'n/a (no WAL files yet)' })"
Write-Host ''
Write-Host 'Next: ensure WAL archiving is active for this cluster, and insert more WAL files by running pg_switch_wal periodically.' -ForegroundColor Yellow