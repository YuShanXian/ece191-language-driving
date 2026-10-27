param(
 [Parameter(Mandatory=$true)][string]$Instruction,
 [ValidateRange(1,7)][int]$Scene=1,
 [string]$Model='gpt-5.6-luna',
 [ValidateSet('low','medium','high')][string]$Reasoning='low',
 [string]$StartStateJson,
 [switch]$Plan
)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$config=Join-Path $root 'config\language-parser-v4'
$run=Join-Path $root ('runs\project-v3\llm-parser-v4\'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff')+'-'+[guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $run -Force | Out-Null
$output=Join-Path $run 'parsed.json'
$prompt=(Get-Content -LiteralPath (Join-Path $config 'prompt.txt') -Raw)+"`nPASSENGER INPUT (JSON string):`n"+(ConvertTo-Json -InputObject $Instruction -Compress)
@{instruction=$Instruction;scene=$Scene;model=$Model;reasoning=$Reasoning;prompt_version='v4';time=(Get-Date -Format o)} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $run 'request.json') -Encoding utf8
$prompt | & codex exec --ignore-user-config --ephemeral --skip-git-repo-check --sandbox read-only -C $run -m $Model -c "model_reasoning_effort=$Reasoning" --output-schema (Join-Path $config 'schema.json') -o $output --json - 1> (Join-Path $run 'events.jsonl') 2> (Join-Path $run 'stderr.log')
if($LASTEXITCODE -ne 0){throw "LLM call failed. See $run\stderr.log; no trajectory selected."}
$r=Get-Content -LiteralPath $output -Raw | ConvertFrom-Json
if($r.status -notin @('parsed','needs_clarification')){throw 'Invalid parser status'}
$r | ConvertTo-Json -Depth 15
if($Plan){
 $linuxOutput=$output.Replace('\','/').Replace('D:','historical-drive')
 $cmd="cd historical-project && bash run_wsl.sh execute_language_plan_v4.py --scene $Scene --plan '$linuxOutput'"
 if($StartStateJson){
  $StartStateJson | Set-Content -LiteralPath (Join-Path $run 'start-state.json') -Encoding utf8
  $stateLinux=(Join-Path $run 'start-state.json').Replace('\','/').Replace('D:','historical-drive')
  $cmd+=" --state '$stateLinux'"
 }
 & wsl.exe bash -lc $cmd
 if($LASTEXITCODE -ne 0){throw 'Offline execution failed'}
}
Write-Output "Saved run: $run"
