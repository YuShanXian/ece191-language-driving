import tempfile,json
from pathlib import Path
from mtr_candidate_review_store import save_candidates,read_reviews
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'choices.json';save_candidates(p,{'scene':1,'command':0,'mode':'selected','candidate_ids':[64,2]});assert read_reviews(p)['reviews'][0]['candidate_ids']==[2,64]
 save_candidates(p,{'scene':1,'command':1,'mode':'none','candidate_ids':[]});save_candidates(p,{'scene':1,'command':0,'mode':'selected','candidate_ids':[2]});assert len(read_reviews(p)['reviews'])==2
 before=p.read_bytes()
 for ids,mode in [([65],'selected'),([1,1],'selected'),([True],'selected'),([],'selected'),([1],'none')]:
  try:save_candidates(p,{'scene':1,'command':0,'mode':mode,'candidate_ids':ids})
  except ValueError:pass
  else:raise AssertionError((ids,mode))
 assert p.read_bytes()==before
root=Path('historical-project/runs/project-v3/automatic-road-v9');data=json.loads((root/'candidate-picker-data.json').read_text())
assert len(data['scenes'])==7
for s in data['scenes'].values():
 assert [r['id'] for r in s['candidates']]==list(range(1,65));assert len(s['commands'])==5
 assert all(len(r['points'])==61 and len(r['smoothed'])==61 for r in s['candidates'])
print('Persistence, independent rows, multi-selection, invalid input, 448 candidate IDs and 35 panels verified. Real reviews untouched.')
