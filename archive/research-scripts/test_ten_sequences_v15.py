import sys,json,subprocess,itertools
from pathlib import Path
r=Path(r'historical-project');sys.path.insert(0,str(r/'scripts'));from parser_backends import parse
out=r/'runs/project-v3/multistep-v15';state=json.loads((out/'state.json').read_text());items=[('drive forward 6 meters and stop','go_straight',6,None),('back up 3 meters and stop','reverse',3,None),('set the speed to 10 km/h','set_speed',None,10/3.6),('drive ahead 4 meters and stop','go_straight',4,None),('reverse 2 meters and stop','reverse',2,None)]
orders=[(0,1,2,3,4),(4,3,2,1,0),(2,0,4,3,1),(1,2,3,4,0),(3,4,0,1,2),(0,3,1,4,2),(4,1,2,0,3),(2,4,3,0,1),(1,0,3,2,4),(3,2,1,0,4)]
results=[]
for i,order in enumerate(orders):
 words=[items[j][0] for j in order]
 if i>=8:
  zh=['\u5411\u524d\u5f006\u7c73\u5e76\u505c\u8f66','\u5012\u8f663\u7c73\u5e76\u505c\u8f66','\u901f\u5ea6\u8bbe\u4e3a\u6bcf\u5c0f\u65f610\u516c\u91cc','\u5411\u524d\u5f004\u7c73\u5e76\u505c\u8f66','\u5012\u8f662\u7c73\u5e76\u505c\u8f66'];words=[zh[j] for j in order]
 text=', '.join(words)+'.';x=parse(text,'claude-sonnet-5-5');p=x['parsed'];d=Path(x['run']);(d/'start-state.json').write_text(json.dumps(state));actual=p.get('stages',[]);expected=[items[j] for j in order];correct=len(actual)==5 and all(a['action']==b[1] and a.get('travel_distance_m')==b[2] and (b[3] is None or abs((a.get('target_speed_mps') or 0)-b[3])<.01) for a,b in zip(actual,expected))
 lp=str(d).replace('\\','/').replace('D:','historical-drive');z=subprocess.run(['wsl.exe','bash','-lc',f'cd historical-project && bash run_wsl.sh execute_language_plan_v4.py --scene 7 --plan {lp}/parsed.json --state {lp}/start-state.json --mode free'],capture_output=True,text=True);e=json.loads((d/'execution.json').read_text()) if z.returncode==0 else {'status':'error','error':z.stderr[-1000:]}
 er=e.get('stages',[]);executed=e['status']=='completed_offline' and [s['action'] for s in er]==[b[1] for b in expected] and all(s.get('start_point',0)==er[k-1].get('end_point',0) for k,s in enumerate(er) if k>0)
 row={'group':i+1,'input':text,'expected':[{'action':b[1],'distance':b[2]} for b in expected],'actual':[{'action':s['action'],'distance':s.get('travel_distance_m')} for s in actual],'order_correct':correct,'execution_complete_in_order':executed,'execution_status':e['status'],'stages':er,'error':e.get('error'),'run':str(d)};results.append(row);(out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'group':i+1,'order':correct,'execution':executed,'status':e['status']}),flush=True)
