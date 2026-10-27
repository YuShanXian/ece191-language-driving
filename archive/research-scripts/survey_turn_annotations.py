"""Inventory single unconditional turns before choosing any additional records."""
from collections import Counter
from dataclasses import asdict
import json
from mtr_project.annotations import load_release
from mtr_project.language import parse_instruction
from mtr_project.paths import ROOT,sha256,write_json


def main():
    path=ROOT/'references/release_annotationsV1.csv';records,metadata=load_release(path)
    existing={p.stem for p in (ROOT/'data/nuplan/db').glob('*.db')}
    used_recordings={clip.rsplit('_',2)[0] for clip in existing};rows=[]
    for record in records:
        parsed=parse_instruction(record.instruction)
        if parsed['status']!='parsed' or len(parsed['stages'])!=1:continue
        stage=parsed['stages'][0]
        if stage['action'] not in ['turn_left','turn_right'] or stage['trigger']['kind']!='now':continue
        rows.append({**asdict(record),'action':stage['action'],'db_present':record.clip_id in existing,'recording_seen':record.recording_id in used_recordings})
    report={'annotation_source_sha256':sha256(path),'selection':'Inventory only: complete single unconditional turn instruction; no model output or success filtering.',
            'total':len(rows),'by_action':dict(Counter(r['action'] for r in rows)),'new_recording_rows':sum(not r['recording_seen'] for r in rows),'rows':rows}
    write_json(ROOT/'runs/project-v2/catalog/turn-annotation-survey.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
    print(json.dumps(rows[:15],indent=2))


if __name__=='__main__':main()
