import sys,json,subprocess
from pathlib import Path
r=Path(r'historical-project');sys.path.insert(0,str(r/'scripts'))
from parser_backends import parse
out=r/'runs/project-v3/basic-commands-v14';out.mkdir(exist_ok=True)
cases=[('Stop immediately.',['emergency_stop']),('Cancel the current instruction.',['cancel']),('\u4fdd\u6301\u505c\u8f66',['hold_stopped']),('Resume driving.',['resume']),('Keep backing up.',['reverse_continuous']),('\u5012\u8f6610\u7c73，\u7136\u540e\u524d\u8fdb20\u7c73\u5e76\u505c\u8f66',['reverse','go_straight']),('Back up 5 meters, then back up another 5 meters.',['reverse','reverse']),('Pull over to the right and stop.',['pull_over']),('\u9760\u5de6\u8fb9\u505c\u8f66',['pull_over']),('Park here.',['park']),('Move forward 15 meters and stop.',['go_straight']),('Switch two lanes to the left.',['lane_change_left']),('Use the second lane from the right.',['select_lane']),('Brake now!',['emergency_stop']),('Slow down a little.',['slow_down']),('Go at 20 km/h.',['set_speed'])]
state=json.loads((r/'runs/project-v3/recording-demo-v1/resume-state.json').read_text());results=[]
for i,(text,expected) in enumerate(cases):
 try:
  x=parse(text,'claude-sonnet-5-5');p=x['parsed'];d=Path(x['run']);(d/'start-state.json').write_text(json.dumps(state))
  lp=str(d).replace('\\','/').replace('D:','historical-drive');cmd=f'cd historical-project && bash run_wsl.sh execute_language_plan_v4.py --scene 7 --plan {lp}/parsed.json --state {lp}/start-state.json --mode free'
  z=subprocess.run(['wsl.exe','bash','-lc',cmd],capture_output=True,text=True)
  e=json.loads((d/'execution.json').read_text()) if z.returncode==0 else {'status':'error','error':z.stderr[-2000:]}
  acts=[s['action'] for s in p.get('stages',[])];okay=acts==expected and e['status'] in ('completed_offline','live_control')
  row={'case':i,'text':text,'expected':expected,'actions':acts,'passed':okay,'status':e['status'],'stages':e.get('stages',[]),'error':e.get('error'),'run':str(d)}
 except Exception as ex:row={'case':i,'text':text,'passed':False,'error':str(ex)}
 results.append(row);(out/'tests.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(row,ensure_ascii=False),flush=True)
