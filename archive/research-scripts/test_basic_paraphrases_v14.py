from pathlib import Path
import sys,json
r=Path(r'historical-project');sys.path.insert(0,str(r/'scripts'));from parser_backends import parse
cases=[('Back the car up a little.',['reverse']),('Roll backwards 8 metres.',['reverse']),('\u5012\u9000\u4e94\u7c73，\u518d\u5f80\u524d\u5f00\u5341\u7c73\u505c\u4e0b',['reverse','go_straight']),('Stop right now!',['emergency_stop','stop']),('Abort the current maneuver.',['cancel']),('Keep the car stationary.',['hold_stopped']),('Carry on driving.',['resume','continuous_drive']),('Pull off to the left side of the road.',['pull_over']),('Set the speed to the maximum.',['set_speed']),('Ease off a bit.',['slow_down']),('Pick up the pace.',['speed_up']),('Move over one lane to my right.',['lane_change_right'])]
results=[]
for text,expected in cases:
 x=parse(text,'claude-sonnet-5-5');p=x['parsed'];a=[s['action'] for s in p.get('stages',[])];ok=a==expected if len(expected)>1 and 'reverse' in expected else len(a)==1 and a[0] in expected
 row={'text':text,'actions':a,'understood':ok,'status':p['status'],'run':x['run']};results.append(row);print(json.dumps(row,ensure_ascii=False),flush=True);(r/'runs/project-v3/basic-commands-v14/paraphrases.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
