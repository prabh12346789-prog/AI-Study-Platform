param(
    [string]$DailyAt = "07:00",
    [string]$TaskName = "UPSC AI Mentor - Daily Current Affairs"
)

$ErrorActionPreference = "Stop"

$backend = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $backend ".venv\Scripts\python.exe"
$runner = Join-Path $backend "scripts\run_daily_current_affairs.py"
if (-not (Test-Path -LiteralPath $python)) { throw "Project virtual environment not found: $python" }

$action = New-ScheduledTaskAction -Execute $python -Argument ('"{0}"' -f $runner) -WorkingDirectory $backend
$trigger = New-ScheduledTaskTrigger -Daily -At $DailyAt
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Collects allowlisted UPSC Current Affairs into the local AI Study Platform. Secrets remain in backend/.env." -Force
Get-ScheduledTask -TaskName $TaskName
