$ErrorActionPreference='Stop'
$taskName='ECE191 Driving Demo'
$task=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if(-not $task){throw 'Install the ECE191 Driving Demo background task first.'}
if($task.State -eq 'Disabled'){Enable-ScheduledTask -TaskName $taskName | Out-Null}
Start-ScheduledTask -TaskName $taskName
Write-Host 'Demo background task started. Open http://localhost:8775. This window can be closed.'
