"""Unordered human choices of raw MTR candidate IDs; separate from road labels."""
from automatic_review_store import LOCK,read_reviews
from datetime import datetime,timezone
import json,os

def save_candidates(path,value):
 if not isinstance(value,dict):raise ValueError('invalid object')
 s=value.get('scene');c=value.get('command');ids=value.get('candidate_ids');mode=value.get('mode')
 if type(s) is not int or not 1<=s<=7 or type(c) is not int or not 0<=c<=4:raise ValueError('invalid scene/command')
 if not isinstance(ids,list) or any(type(i) is not int or not 1<=i<=64 for i in ids) or len(ids)!=len(set(ids)):raise ValueError('invalid candidates')
 if mode not in ('unreviewed','selected','none','uncertain') or (mode=='selected')!=bool(ids):raise ValueError('inconsistent mode')
 row={'scene':s,'command':c,'candidate_ids':sorted(ids),'mode':mode,'representation':'raw_world_xy','selection_semantics':'unordered_feasible_alternatives','updated_at':datetime.now(timezone.utc).isoformat()}
 with LOCK:
  data=read_reviews(path);data['reviews']=[r for r in data['reviews'] if (r['scene'],r['command'])!=(s,c)]+[row];data['reviews'].sort(key=lambda r:(r['scene'],r['command']));path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,path)
 return row
