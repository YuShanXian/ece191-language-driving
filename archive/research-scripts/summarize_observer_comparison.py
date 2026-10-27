"""Compare detected events; no human-verified event truth is available yet."""
import json
from mtr_project.paths import ROOT,write_json,sha256


def events(report):
    return [{'action':action,'timestamp_us':row['timestamp_us'],
             'seconds_from_first_lidar':row['seconds_from_first_lidar']}
            for row in report['trace'] for action in row['observed_actions']]


def main():
    folder=ROOT/'runs/project-v2/replay';rows=[]
    names=['doplan_006160-window-v2','development-00-illustration','development-01-observer-audit','development-02-observer-audit']
    for name in names:
        before_path=folder/f'{name}.json';after_path=folder/f'{name}-corridor-v1.json'
        before=json.loads(before_path.read_text());after=json.loads(after_path.read_text())
        if after['comparison_source_sha256']!=sha256(before_path):raise ValueError('Comparison input changed')
        a=events(before);b=events(after);matched=set();new=[]
        for event in b:
            possible=[(abs(event['timestamp_us']-old['timestamp_us']),i) for i,old in enumerate(a)
                      if i not in matched and event['action']==old['action']]
            if possible and min(possible)[0]<=2_000_000:matched.add(min(possible)[1])
            else:new.append(event)
        rows.append({'replay':name,'clip':before['source_clip'],'frames':before['frames'],
                     'baseline_counts':before['observed_action_counts'],'experiment_counts':after['observed_action_counts'],
                     'new_or_more_than_two_seconds_shifted_events':new,
                     'baseline_events_without_experimental_match':[e for i,e in enumerate(a) if i not in matched],
                     'baseline_sha256':sha256(before_path),'experiment_sha256':sha256(after_path)})
    result={'observer':'connector_corridor_experiment_v1','recordings':len(rows),'comparisons':rows,
            'design_clip':'2021.06.09.12.39.51_veh-26_05332_05540',
            'scope':'Designed after inspecting the original doPlan example. Three development drives are additional diagnostics. Extra events need manual video/map review; counts are not precision, recall, or closed-loop success.'}
    write_json(ROOT/'runs/project-v2/replay-diagnostics/observer-comparison.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
