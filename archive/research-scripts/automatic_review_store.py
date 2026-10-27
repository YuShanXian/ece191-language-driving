"""Local review persistence, independent of automatic evaluation results."""
import json,os,threading
from pathlib import Path
from datetime import datetime,timezone
LOCK=threading.Lock()
def read_reviews(path):
 return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schema':1,'reviews':[]}
def save_review(path,value):
 if not isinstance(value,dict):raise ValueError('invalid review')
 s=value.get('scene');c=value.get('command');v=value.get('verdict');note=value.get('comment')
 if type(s) is not int or not 1<=s<=7 or type(c) is not int or not 0<=c<=4:raise ValueError('invalid scene/command')
 if v not in ('','pass','fail','uncertain') or not isinstance(note,str) or len(note)>10000:raise ValueError('invalid verdict/comment')
 row={'scene':s,'command':c,'verdict':v,'comment':note,'updated_at':datetime.now(timezone.utc).isoformat()}
 with LOCK:
  data=read_reviews(path);data['reviews']=[r for r in data['reviews'] if (r['scene'],r['command'])!=(s,c)]+[row];data['reviews'].sort(key=lambda r:(r['scene'],r['command']));path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,path)
 return row
