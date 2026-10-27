"""Independent per-command human road targets; never modifies verdicts or routes."""
import json,os,threading
from datetime import datetime,timezone
LOCK=threading.Lock()

def blank_targets():
 return {'schema':2,'selection_semantics':'feasible_alternatives','map_version':'v7-map-1','reviews':[{'scene':s,'command':c,'mode':'unselected','road_ids':[]} for s in range(1,8) for c in range(5)]}

def validate_target(row,maps):
 if not isinstance(row,dict):raise ValueError('object required')
 s=row.get('scene');c=row.get('command')
 if type(s) is not int or not 1<=s<=7 or type(c) is not int or not 0<=c<=4:raise ValueError('scene/command')
 mode=row.get('mode');ids=row.get('road_ids')
 if mode not in ('unselected','roads','none','continue','uncertain'):raise ValueError('mode')
 if not isinstance(ids,list) or len(ids)>40 or any(not isinstance(k,str) for k in ids) or len(set(ids))!=len(ids):raise ValueError('road alternatives')
 known={n['id'] for n in maps[str(s)]['roads']}
 if any(k not in known for k in ids):raise ValueError('unknown road for scene')
 if mode!='roads' and ids:raise ValueError('contradictory selection')
 return {'scene':s,'command':c,'mode':mode,'road_ids':sorted(ids),'selection_semantics':'feasible_alternatives','updated_at':datetime.now(timezone.utc).isoformat()}

def update_target(path,row,maps):
 validated=validate_target(row,maps)
 with LOCK:
  data=json.loads(path.read_text(encoding='utf-8')) if path.exists() else blank_targets()
  data['schema']=2;data['selection_semantics']='feasible_alternatives'
  index=(validated['scene']-1)*5+validated['command'];data['reviews'][index]=validated
  temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temp,path)
 return validated
