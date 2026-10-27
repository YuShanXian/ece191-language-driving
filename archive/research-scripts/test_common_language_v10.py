import json,time,sys
from pathlib import Path
from parser_backends import parse
ROOT=Path(r'historical-project');OUT=ROOT/'runs/project-v3/common-commands-v10';OUT.mkdir(exist_ok=True)
# Freeze expected meanings before making model calls. Conditions must never be removed.
CASES=[
('set to the highest speed',['set_speed'],15),('Could you set it to the maximum speed, please?',['set_speed'],15),('Go at top speed.',['set_speed'],15),('Full speed, please.',['set_speed'],15),('Drive as fast as possible.',['set_speed'],15),('use the max speed[',['set_speed'],15),('\u628a\u901f\u5ea6\u8c03\u5230\u6700\u5feb',['set_speed'],15),('\u5f00\u5230\u6700\u9ad8\u901f\u5ea6',['set_speed'],15),
('Set the speed to 30 km/h.',['set_speed'],30/3.6),('Can we do 20 mph?',['set_speed'],20*.44704),('Drive at 5 meters per second.',['set_speed'],5),('\u901f\u5ea6\u8bbe\u6210\u6bcf\u5c0f\u65f618\u516c\u91cc',['set_speed'],5),
('A little faster, please.',['speed_up'],None),('Speed up a bit.',['speed_up'],None),('Slow down, please.',['slow_down'],None),('\u5f00\u6162\u4e00\u70b9',['slow_down'],None),
('make an uturn',['u_turn'],None),('Make a U turn.',['u_turn'],None),('Turn around and head back.',['u_turn'],None),('Please do a 180-degree turn.',['u_turn'],None),('\u5728\u8fd9\u91cc\u8c03\u5934',['u_turn'],None),('\u6389\u5934\u56de\u53bb',['u_turn'],None),
('Take a left.',['turn_left'],None),('Could you turn right?',['turn_right'],None),('Move over one lane to the left.',['lane_change_left'],None),('Switch to the lane on the right.',['lane_change_right'],None),('Get into the far-right lane.',['select_lane'],None),('\u8fdb\u5165\u6700\u5de6\u8fb9\u7684\u8f66\u9053',['select_lane'],None),
('Keep following this road.',['continuous_drive'],None),('Keep going until the road ends.',['continuous_drive'],None),('Stop the car.',['stop'],None),('\u7ee7\u7eed\u5f00',['resume','continuous_drive'],None),
('Drive for 50 meters, then stop.',['go_straight'],None),('Go another 0.05 km and stop.',['go_straight'],None),('\u5f80\u524d\u5f0030\u7c73\u7136\u540e\u505c\u8f66',['go_straight'],None),
('turn left, than move to the rightmost lane, use the highest speed.',['turn_left','select_lane','set_speed'],15),('Make a U-turn, then drive 60 meters and stop.',['u_turn','go_straight'],None),('First turn right, then drive 20 metres and stop.',['turn_right','go_straight'],None),('\u5148\u8c03\u5934，\u7136\u540e\u4ee5\u6bcf\u5c0f\u65f618\u516c\u91cc\u5f0030\u7c73\u5e76\u505c\u8f66',['u_turn','go_straight'],5),
('Do not turn left.',['NO_ACTION'],None),('Set speed to 20.',['CLARIFY'],None),('Turn left when the light turns green.',['CONDITION'],None),('Follow the black SUV.',['GROUNDING'],None),('Left.',['CLARIFY'],None),
]
def grade(p,expected,speed):
 stages=p.get('stages',[]);acts=[s['action'] for s in stages];errors=[]
 if expected==['CLARIFY']:
  return [] if p['status']=='needs_clarification' else ['Should ask for clarification']
 if expected==['NO_ACTION']:
  return [] if not stages or all(s['action']=='unsupported' for s in stages) else ['Negation became positive action']
 if expected==['CONDITION']:
  return [] if stages and stages[0]['trigger'] not in ('now','after_previous') else ['Condition discarded']
 if expected==['GROUNDING']:
  return [] if p.get('unresolved_text') or any(s.get('target_text') or s.get('constraints') for s in stages) else ['Vehicle reference discarded']
 if expected==['resume','continuous_drive']:
  if acts not in [['resume'],['continuous_drive']]:errors.append('Expected resume or continuous drive')
 elif expected==['u_turn'] and acts==['u_turn','continuous_drive']:pass # Equivalent expanded interpretation of head back.
 elif acts!=expected:errors.append('Actions/order: '+str(acts)+' expected '+str(expected))
 if p['status']!='parsed' or p.get('unresolved_text'):errors.append('Unexpected clarification')
 if speed is not None and not any(abs((s.get('target_speed_mps') or 0)-speed)<.001 for s in stages):errors.append('Wrong speed or units')
 return errors

if __name__=='__main__':
 path=OUT/'language-results.json';results=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
 for i,(text,actions,speed) in enumerate(CASES):
  if any(r['case']==i for r in results):continue
  try:
   r=parse(text,'claude-sonnet-5-5');errors=grade(r['parsed'],actions,speed)
   item={'case':i,'text':text,'expected':actions,'expected_speed':speed,'semantic_passed':not errors,'errors':errors,'parsed':r['parsed'],'run':r['run'],'seconds':r['seconds']}
  except Exception as e:item={'case':i,'text':text,'expected':actions,'semantic_passed':False,'errors':[str(e)]}
  results.append(item);path.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in item.items() if k not in ('parsed','run')},ensure_ascii=False),flush=True)
