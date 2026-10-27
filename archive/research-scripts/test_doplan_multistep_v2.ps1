$cases=@(@{id='doplan_006160';scene=1},@{id='doplan_000567';scene=3},@{id='doplan_002902';scene=5},@{id='doplan_001838';scene=6},@{id='doplan_003247';scene=5},@{id='doplan_005348';scene=5},@{id='doplan_000013';scene=7},@{id='doplan_004144';scene=7},@{id='doplan_000861';scene=3})
$rows=Import-Csv 'historical-project\references\release_annotationsV1.csv'
foreach($case in $cases){
 $row=$rows | Where-Object annotation_id -eq $case.id | Select-Object -First 1
 Write-Output "TEST $($case.id) SCENE $($case.scene)"
 & 'historical-project\scripts\parse_navigation_llm_v2.ps1' -Instruction $row.passenger_instruction -Scene $case.scene -Plan
}
