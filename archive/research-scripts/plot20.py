exec(open('historical-project/scripts/direct_worker_v19.py').read().split('for line in sys.stdin:')[0])
import math
import matplotlib
matplotlib.use('Agg')
import math
import matplotlib.pyplot as plt
from pathlib import Path
from trajectory_checks import angle_diff
rows=[json.loads(l) for l in open('historical-project/runs/project-v3/recording-demo-v1/command-history.jsonl')];ids=['ui-1792575941373','ui-1792575976876'];fig,axs=plt.subplots(1,2,figsize=(14,7));results=[]
for ax,id in zip(axs,ids):
 r=next(r for r in rows if r.get('status')=='received' and r['id']==id);state=r['state'];g,c,rot=free_navigation_v8.context(7);origin=np.array(state['xy'])
 for node in g.nodes.values():
  xy=(np.asarray(node.baseline.coords)[:,:2]-c[:2])@rot
  if np.min(np.linalg.norm(xy-origin,axis=1))<65:ax.plot(xy[:,0],xy[:,1],color='#c8d0d8',lw=1)
 for action,color in [('turn_right','#007e9b'),('go_straight','#e48b17')]:
  st=dict(action=action,source_clause=action,trigger='now',trigger_text='',trigger_value=None,target_text='',lane_reference='none',lane_number=None,completion_text='',constraints=[],travel_distance_m=None,stop_at_end=False,target_speed_mps=None)
  e=execute(7,{'status':'parsed','stages':[st],'unresolved_text':[]},state,'free');xy=np.array(e['points']);delta=xy[-1]-xy[-min(5,len(xy))];angle=math.degrees(angle_diff(math.atan2(delta[1],delta[0]),state['heading']));results.append({'id':id,'action':action,'status':e['status'],'exit_heading_change_deg':angle,'stages':e['stages']})
  assert e['status']=='completed_offline'
  if action=='turn_right':assert angle<-30
  ax.plot(xy[:,0],xy[:,1],lw=3,label=('Straight unavailable: follow bend' if any(s.get('instruction_followed') is False for s in e['stages']) else action.replace('_',' ')));ax.scatter(*xy[-1],color=color)
 ax.scatter(*origin,color='black',s=50,label='Current position');ax.set_aspect('equal');ax.set_xlim(origin[0]-50,origin[0]+50);ax.set_ylim(origin[1]-55,origin[1]+55);ax.legend();ax.set_title('Inside junction: keep exit choices' if id==ids[0] else 'Right turn: prepare in adjacent lane');ax.set_xlabel('x (m)');ax.set_ylabel('y (m)')
out=Path('historical-project/runs/project-v3/navigation-fix-v20');(out/'direction-check.json').write_text(json.dumps(results,indent=2));fig.tight_layout();fig.savefig(out/'direction-check.png',dpi=150);print([(r['action'],round(r['exit_heading_change_deg'],1)) for r in results])



