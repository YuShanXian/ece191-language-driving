$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$logRoot=Join-Path $projectRoot 'runs\project-v3\demo-service-v26'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$lock=$null
try {$lock=[IO.File]::Open((Join-Path $logRoot 'supervisor.lock'),'OpenOrCreate','ReadWrite','None')} catch {exit 0}
$node=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
$serverPath=Join-Path $PSScriptRoot 'serve_recording_demo.cjs'
$env:ECE191_ROOT=$projectRoot
$env:DEMO_BASE=Join-Path $projectRoot 'runs\project-v3\recording-demo-v1'
$env:DEMO_PORT='8775'
$env:DEMO_WORKER_PATH=$null
$env:ECE191_PARSER_PROMPT=Join-Path $projectRoot 'config\language-parser-v4\prompt.txt'
$env:DEMO_CATALOG=Join-Path $projectRoot 'config\language-parser-v4\demo-models.json'
function Write-ServiceEvent($event,$detail) {
 @{time=[DateTimeOffset]::Now.ToString('o');event=$event;detail=$detail} | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $logRoot 'supervisor.jsonl') -Encoding utf8
}
function Get-DemoHealth {
 try {Invoke-RestMethod -Uri 'http://127.0.0.1:8775/health' -TimeoutSec 5 -UseBasicParsing} catch {$null}
}
Write-ServiceEvent 'supervisor_started' @{pid=$PID}
try {
 while($true) {
  $listener=Get-NetTCPConnection -LocalPort 8775 -State Listen -ErrorAction SilentlyContinue
  if($listener) {
   $owner=Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
   if($owner.Name -ne 'node.exe' -or -not $owner.CommandLine.Contains($serverPath)) {
    Write-ServiceEvent 'port_busy' 'An unrecognized listener owns port 8775; it was not stopped.'
    Start-Sleep -Seconds 20;continue
   }
   # Recover supervision after a supervisor restart without disrupting a healthy server.
   $server=Get-Process -Id $owner.ProcessId
   Write-ServiceEvent 'server_adopted' @{pid=$server.Id}
  } else {
   $stamp=Get-Date -Format 'yyyyMMdd-HHmmss-fff'
   $server=Start-Process -FilePath $node -ArgumentList @($serverPath) -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logRoot "$stamp.stdout.log") -RedirectStandardError (Join-Path $logRoot "$stamp.stderr.log") -PassThru
   Write-ServiceEvent 'server_started' @{pid=$server.Id;log_prefix=$stamp}
  }
  $failures=0
  while(-not $server.WaitForExit(10000)) {
   $health=Get-DemoHealth
   if($health.service -eq 'ece191-driving-demo' -and $health.pid -eq $server.Id) {$failures=0;continue}
   $failures++
   if($failures -ge 3) {
    # Stop only this supervisor's own server tree, never an unrelated listener.
    Write-ServiceEvent 'health_restart' @{pid=$server.Id;failed_checks=$failures}
    & "$env:SystemRoot\System32\taskkill.exe" /PID $server.Id /T /F | Out-Null
    break
   }
  }
  $server.Refresh()
  Write-ServiceEvent 'server_exited' @{pid=$server.Id;exit_code=$(if($server.HasExited){$server.ExitCode}else{$null})}
  $server.Dispose()
  Start-Sleep -Seconds 3
 }
} finally {$lock.Dispose()}
