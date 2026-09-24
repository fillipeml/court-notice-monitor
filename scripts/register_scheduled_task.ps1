# Registers the daily sweep in Windows Task Scheduler (current user):
#   CourtNoticeMonitor-Sweep - business days at 08:00
# Each run appends to logs\sweep-YYYY-MM-DD.log.
#
# Keep this file 100% ASCII: PowerShell 5.1 reads a .ps1 without BOM as ANSI, and a
# typographic dash or quote corrupts the parse.
#
# Remove with:
#   Unregister-ScheduledTask -TaskName "CourtNoticeMonitor-Sweep" -Confirm:$false

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force $logDir | Out-Null

# cmd /c to redirect the log with a date; working directory pinned to the repository root
$command = "/c cd /d `"$root`" && uv run notice-monitor >> `"$logDir\sweep-%DATE:~6,4%-%DATE:~3,2%-%DATE:~0,2%.log`" 2>&1"

$weekdays = @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $command -WorkingDirectory $root
# AllowStartIfOnBatteries: without it Windows does NOT start the task on a laptop running on
# battery (a real missed run). WakeToRun tries to wake a sleeping machine at the scheduled time.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $weekdays -At "08:00"
Register-ScheduledTask -TaskName "CourtNoticeMonitor-Sweep" -Action $action -Trigger $trigger `
    -Settings $settings -Description "Read-only sweep of the electronic judicial domicile" `
    -Force | Out-Null
Write-Output "Task registered: CourtNoticeMonitor-Sweep (08:00, business days, StartWhenAvailable)"
Write-Output "Check with: Get-ScheduledTask -TaskName 'CourtNoticeMonitor-*'"
