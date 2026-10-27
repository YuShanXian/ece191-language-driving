"""Fixed button actions. No language model or text parsing."""
import argparse,json,subprocess,uuid
from pathlib import Path
ROOT=Path('historical-project')
ACTIONS={'go_straight','turn_left','turn_right','lane_change_left','lane_change_right','u_turn','reverse','pull_over','emergency_stop','cancel','resume','continuous_drive'}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--action',required=True,choices=sorted(ACTIONS));a.add_argument('--scene',required=True,type=int,choices=range(1,8));a.add_argument('--state');a.add_argument('--mode',choices=['free','safe'],default='free');args=a.parse_args()
 stage=dict(action=args.action,source_clause=args.action.replace('_',' '),trigger='now',trigger_text='',trigger_value=None,target_text='',lane_reference='rightmost' if args.action=='pull_over' else 'none',lane_number=None,completion_text='',constraints=[],travel_distance_m=10 if args.action=='reverse' else None,stop_at_end=args.action in ('reverse','pull_over'),target_speed_mps=None)
 plan={'status':'parsed','stages':[stage],'unresolved_text':[],'explanation':'Direct command: '+stage['source_clause']+'. No language model used.'};folder=ROOT/'runs/project-v3/direct-commands-v18'/str(uuid.uuid4());folder.mkdir(parents=True);(folder/'parsed.json').write_text(json.dumps(plan));(folder/'request.json').write_text(json.dumps(vars(args)))
 linux=str(folder).replace('\\','/').replace('D:','historical-drive');cmd=f'cd historical-project && bash run_wsl.sh scripts/execute_language_plan_v4.py --scene {args.scene} --plan {linux}/parsed.json --mode {args.mode}'
 if args.state:(folder/'start-state.json').write_text(args.state);cmd+=' --state '+linux+'/start-state.json'
 subprocess.run(['wsl.exe','bash','-lc',cmd],check=True,capture_output=True);plan['execution']=json.loads((folder/'execution.json').read_text());plan['model_info']={'id':'direct','parser_seconds':0};print(json.dumps(plan))
