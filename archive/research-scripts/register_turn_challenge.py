"""Fix four new-recording turn-context clips using metadata only, before inference."""
import json
from mtr_project.paths import ROOT,sha256,write_json


def main():
    source=ROOT/'runs/project-v2/catalog/turn-annotation-survey.json';survey=json.loads(source.read_text())
    catalogs=sorted((ROOT/'runs/project-v2/catalog').glob('nuplan-v1.1_train_vegas_*.zip.json'))
    members={r['clip']:r for p in catalogs for r in json.loads(p.read_text())['members']}
    rows=[r for r in survey['rows'] if not r['recording_seen'] and r['clip_id'] in members and members[r['clip_id']]['bytes']<=150*1024**2]
    chosen=[];used=set()
    for action in ['turn_left','turn_right']:
        candidates=sorted([r for r in rows if r['action']==action],key=lambda r:(members[r['clip_id']]['bytes'],r['clip_id'],r['annotation_id']))
        count=0
        for row in candidates:
            recording=row['clip_id'].rsplit('_',2)[0]
            if recording in used:continue
            chosen.append({**members[row['clip_id']],'recording_id':recording,'context_annotation':row})
            used.add(recording);count+=1
            if count==2:break
        if count!=2:raise ValueError('Insufficient new recordings; do not silently relax selection')
    result={'tag':'turn-challenge-v1','selection_rule':'Two clips per unconditional turn direction from previously unseen recordings in the six cached official Vegas catalogs; <=150MiB each; ascending DB size then clip then annotation ID; unique recordings across all four. No model outputs used.',
            'selected':chosen,'total_uncompressed_bytes':sum(r['bytes'] for r in chosen),'fractions':[.2,.5,.8],
            'tag_anchors':{'types':['ego_turning_left','ego_turning_right'],'rule':'Per clip and tag type, take earliest tagged lidar time with 4s of earlier log and 4s later log; anchor2s before it, leaving2s history and6s future. Missing types produce an explicit missing row, no replacement search.'},
            'instruction_scope':'Run fixed left/right diagnostic instructions at every anchor. Annotation only selects turn-context recordings; its frames are not assumed aligned and not used as instruction activation.',
            'evaluation_scope':'New-recording coverage challenge with deliberately turn-enriched context; not representative driving, language-ground-truth accuracy or closed-loop success. Official tags may use recorded behavior to choose windows, but no recorded future enters runtime selection.',
            'source_sha256':{str(p.relative_to(ROOT)):sha256(p) for p in [source,*catalogs]},
            'pipeline_rule':'Unchanged pretrained checkpoint, converter, raw64 candidate export and frozen baseline screen. No fitted parameters or relaxed thresholds after examining these outputs.'}
    path=ROOT/'config/turn-challenge-v1.json'
    if path.exists():raise FileExistsError('Preserve the registered plan')
    write_json(path,result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
