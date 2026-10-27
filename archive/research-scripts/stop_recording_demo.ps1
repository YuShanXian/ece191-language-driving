$ErrorActionPreference='Stop'
$taskName='ECE191 Driving Demo'
Disable-ScheduledTask -TaskName $taskName | Out-Null
Stop-ScheduledTask -TaskName $taskName
$serverPath=Join-Path $PSScriptRoot 'serve_recording_demo.cjs'
$listener=Get-NetTCPConnection -LocalPort 8775 -State Listen -ErrorAction SilentlyContinue
if($listener) {
 $server=Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
 if($server.Name -eq 'node.exe' -and $server.CommandLine.Contains($serverPath)) {
  & "$env:SystemRoot\System32\taskkill.exe" /PID $server.ProcessId /T /F | Out-Null
 }
}
Write-Host 'Demo stopped; automatic startup disabled until start_recording_demo.ps1 is run.'
