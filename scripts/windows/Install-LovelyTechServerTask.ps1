param(
    [Parameter(Mandatory=$true)][string]$ProjectRoot,
    [string]$TaskName = "Lovely Tech POS Server"
)
$ErrorActionPreference = "Stop"
$startScript = Join-Path $ProjectRoot "scripts\windows\Start-LovelyTechServer.ps1"
if (-not (Test-Path $startScript)) { throw "Start-LovelyTechServer.ps1 not found under ProjectRoot." }

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = "PT30S"
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "Installed startup task: $TaskName"
Write-Host "It starts Lovely Tech POS 30 seconds after Windows boot and retries after failures."
