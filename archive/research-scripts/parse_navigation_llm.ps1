param(
 [Parameter(Mandatory=$true)][string]$Instruction,
 [ValidateRange(1,7)][int]$Scene=1,
 [string]$Model='gpt-6-astra',
 [ValidateSet('low','medium','high')][string]$Reasoning='medium',
 [switch]$Plan
)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$config=Join-Path $root 'config\language-parser-v1'
$run=Join-Path $root ('runs\project-v3\llm-parser-v1\'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff')+'-'+[guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $run -Force | Out-Null
$output=Join-Path $run 'parsed.json'
$prompt=(Get-Content -LiteralPath (Join-Path $config 'prompt.txt') -Raw)+"`nPASSENGER INPUT (JSON string):`n"+(ConvertTo-Json -InputObject $Instruction -Compress)
@{instruction=$Instruction;scene=$Scene;model=$Model;reasoning=$Reasoning;prompt_version='v1';time=(Get-Date -Format o)} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $run 'request.json') -Encoding utf8
$prompt | & codex exec --ignore-user-config --ephemeral --skip-git-repo-check --sandbox read-only -C $run -m $Model -c "model_reasoning_effort=$Reasoning" --output-schema (Join-Path $config 'schema.json') -o $output --json - 1> (Join-Path $run 'events.jsonl') 2> (Join-Path $run 'stderr.log')
if($LASTEXITCODE -ne 0){throw "LLM call failed. See $run\stderr.log; no trajectory selected."}
$r=Get-Content -LiteralPath $output -Raw | ConvertFrom-Json
$canonical=@{go_straight='Go straight';turn_left='Turn left';turn_right='Turn right';lane_change_left='Change lanes to the left';lane_change_right='Change lanes to the right'}
if($r.status -notin @('ready','needs_clarification','unsupported')){throw 'Invalid parser status'}
if($r.status -eq 'ready' -and ($r.timing -ne 'now' -or $r.condition -ne '' -or -not $canonical.ContainsKey($r.action))){throw 'Invalid executable parse; no trajectory selected.'}
$r | ConvertTo-Json
if($Plan -and $r.status -eq 'ready'){
 # Only fixed canonical strings enter the shell, never passenger text.
 $cmd="cd historical-project && bash run_wsl.sh select_review_instruction.py --scene $Scene --instruction '$($canonical[$r.action])'"
 & wsl.exe bash -lc $cmd | Set-Content -LiteralPath (Join-Path $run 'plan.json') -Encoding utf8
 if($LASTEXITCODE -ne 0){throw 'Offline planner failed'}
 Write-Output "Offline cached trajectory result: $run\plan.json"
}elseif($Plan){Write-Output 'No trajectory selected: instruction requires clarification or an unsupported trigger/sequence.'}
Write-Output "Saved run: $run"
