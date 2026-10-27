import json
from mtr_project.paths import ROOT,write_json
base=ROOT/'runs/project-v3/centerline-planner-v1';rows=json.loads((base/'comparison.json').read_text())['rows'];old=json.loads((ROOT/'runs/project-v3/automatic-road-v9/trajectory-results.json').read_text())['rows'];sources={(r['scene'],r['command']):r['source'] for r in old}
def summarize(rr):
 return {'n':len(rr),'lower_centerline_error':sum(r['new_6s']['mean_centerline_distance_m']<r['old_6s']['mean_centerline_distance_m'] for r in rr),'lower_peak_acceleration':sum(r['new_6s']['motion']['peaks']['acceleration_mps2']<r['old_6s']['motion']['peaks']['acceleration_mps2'] for r in rr),'lower_peak_jerk':sum(r['new_6s']['motion']['peaks']['jerk_mps3']<r['old_6s']['motion']['peaks']['jerk_mps3'] for r in rr),'all_three_lower':sum(r['new_6s']['mean_centerline_distance_m']<r['old_6s']['mean_centerline_distance_m'] and all(r['new_6s']['motion']['peaks'][k]<r['old_6s']['motion']['peaks'][k] for k in ['acceleration_mps2','jerk_mps3']) for r in rr)}
scenes=[]
for s in range(1,8):
 rr=[r for r in rows if r['scene']==s];scenes.append({'scene':s,'old_mean_centerline_m':sum(r['old_6s']['mean_centerline_distance_m'] for r in rr)/5,'new_mean_centerline_m':sum(r['new_6s']['mean_centerline_distance_m'] for r in rr)/5})
audit={'all_35_including_map_fallback':summarize(rows),'mtr_sourced_subset_only':summarize([r for r in rows if sources[r['scene'],r['command']]=='MTR_refined']),'scenes':scenes,'scenes_with_lower_mean_centerline_error':sum(r['new_mean_centerline_m']<r['old_mean_centerline_m'] for r in scenes),'claim':'No evidence of overall superiority in 90% of independent scenes. Counts are descriptive strict inequalities, no significance threshold. MTR subset excludes seven cases where MTR provided no selected output. Same six-second time window, but speed and distance differ. Known development scenes and repeated commands are not independent trials.'}
write_json(base/'performance-audit.json',audit);print(json.dumps(audit,ensure_ascii=False,indent=2))
p=ROOT/'scripts/select_review_instruction.py';s=p.read_text(encoding='utf-8-sig').replace("policy='automatic_roads'","policy='centerline_planner'").replace("default='automatic_roads'","default='centerline_planner'");p.write_text(s,encoding='utf-8')
from select_review_instruction import resolve
for r in rows:
 instruction=['Go straight','Turn left','Turn right','Change lanes to the left','Change lanes to the right'][r['command']];result=resolve(r['scene'],instruction);assert result['policy']=='centerline_planner' and result['result']['source']=='deterministic_map_centerline'
write_json(base/'default-policy-verification.json',{'passed':True,'cases':35,'default_policy':'centerline_planner','mtr_candidates_used':False})
write_json(ROOT/'config/active-planning-strategy.json',{'primary':'deterministic_map_centerline','cli_policy':'centerline_planner','experiment':'runs/project-v3/centerline-planner-v1','mtr_role':'historical_baseline_only','decision':'User-directed engineering choice, not a claim of 90% overall superiority.','date':'2026-10-20'})
