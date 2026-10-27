"""Offline free-mode recovery. Never label synthetic geometry as a mapped route."""
import copy, json, math
import numpy as np
from shapely.geometry import Point, LineString
from mtr_project.paths import ROOT
from execute_language_plan_v3 import execute as finite
from evaluate_candidate_checks import load_graph
from trajectory_checks import tangent, angle_diff

def context(scene):
    w=next(w for w in json.loads((ROOT/'runs/project-v3/automatic-road-v9/input-manifest.json').read_text()) if w['scene']==scene)
    c=json.loads((ROOT/'samples'/w['sample']/'conversion.json').read_text())
    g=load_graph(np.asarray(c['origin_xy_m']),c['source_epsg'],c['source_map'])
    initial=np.load(ROOT/'runs'/w['run']/'internal_0000.npz')['center'].astype(float)
    h=initial[6];rot=np.array([[np.cos(h),-np.sin(h)],[np.sin(h),np.cos(h)]])
    return g,initial,rot

def recover(scene,st,state):
    """Recover map actions only; unresolved language/visual conditions are not bypassed."""
    from navigation_turn_v15 import road_available
    if road_available(scene,state):
        return {'scene':scene,'status':'blocked','points':[state['xy']],'speed_mps':[state['speed']],'dt':.1,'stages':[{'action':st['action'],'source_clause':st['source_clause'],'status':'blocked','reason':'A connected road is still available. Forced recovery is reserved for road ends or off-road positions.'}]}
    g,initial,rot=context(scene)
    p0=initial[:2]+np.asarray(state['xy'])@rot.T;h=initial[6]+state['heading']
    f=np.array([math.cos(h),math.sin(h)]);left=np.array([-f[1],f[0]])
    action=st['action'];distance=st.get('travel_distance_m');guide=[];target=None
    turn=math.pi if action=='u_turn' else math.pi/2 if action=='turn_left' else -math.pi/2 if action=='turn_right' else 0.
    heading=h+turn
    if turn:
        radius=6.;sign=1 if turn>0 else -1
        angles=np.linspace(0,abs(turn),max(30,int(abs(turn)*radius*4)))
        guide=p0+radius*np.sin(angles[:,None])*f+sign*radius*(1-np.cos(angles[:,None]))*left
    elif action in ('lane_change_left','lane_change_right','select_lane'):
        sign=1 if action=='lane_change_left' or (action=='select_lane' and st.get('lane_reference')=='leftmost') else -1
        u=np.linspace(0,1,100);guide=p0+18*u[:,None]*f+sign*3.5*(3*u*u-2*u*u*u)[:,None]*left
    else:guide=np.asarray([p0])
    # Join a nearby lane pointing in the requested direction, even when no graph edge connects it.
    end=np.asarray(guide[-1]);candidates=[]
    view=state.get('view_bounds')
    for node in g.nodes.values():
        if node.kind!='lane':continue
        for reverse in (False,True):
            line=LineString(list(node.baseline.coords)[::-1]) if reverse else node.baseline
            # Inspect the whole visible line, not just its nearest projection.
            for ss in np.unique(np.r_[line.project(Point(end)),np.arange(0,line.length,4)]):
                q=np.asarray(line.interpolate(float(ss)).coords[0])[:2]
                local=(q-initial[:2])@rot
                if view is not None:
                    if not (view[0]<=local[0]<=view[1] and view[2]<=local[1]<=view[3]):continue
                elif np.linalg.norm(q-p0)>state.get('recovery_radius',150):continue
                rel=q-p0;forward=float(rel@f);lateral=float(rel@left)
                if action=='turn_right' and lateral>-2:continue
                if action=='turn_left' and lateral<2:continue
                if action in ('go_straight','keep_lane') and (forward<3 or abs(lateral)>max(5,forward*.7)):continue
                if action in ('lane_change_left','lane_change_right','select_lane') and (abs(lateral)>8 or abs(forward)>25):continue
                if action=='lane_change_left' and lateral<2:continue
                if action=='lane_change_right' and lateral>-2:continue
                a=abs(angle_diff(tangent(line,q),heading));d=float(np.linalg.norm(q-end))
                if a<math.radians(75) and line.length-ss>4:
                    candidates.append((d+10*a+20*reverse,node.key,float(ss),reverse))
    if not candidates and not state.get('expanded_recovery') and action not in ('lane_change_left','lane_change_right','select_lane'):
        expanded={**state,'expanded_recovery':True,'recovery_radius':2000};expanded.pop('view_bounds',None)
        result=recover(scene,st,expanded)
        if result['status']=='completed_offline':
            result['stages'][0]['warning']='Free-mode road recovery: the car was beyond nearby roads; connected back to a mapped road outside the original view.'
        return result
    if not candidates:
        return {'scene':scene,'status':'blocked','stages':[{'index':0,'action':action,'source_clause':st['source_clause'],'status':'blocked','reason':'No road in the visible map can receive the requested direction. Position preserved.','start_point':0,'end_point':0}],'points':[state['xy']],'speed_mps':[state['speed']],'dt':.1}
    if candidates:
        _,target,s,reverse=min(candidates)
        def line_for(key):
            line=g.nodes[key].baseline
            return LineString(list(line.coords)[::-1]) if reverse else line
        line=line_for(target)
        join=min(line.length,s+8);q=np.asarray(line.interpolate(join).coords[0])[:2]
        head=tangent(line,q);L=max(5.,np.linalg.norm(q-end));u=np.linspace(0,1,60)[:,None]
        d0=L*np.array([math.cos(heading),math.sin(heading)]);d1=L*np.array([math.cos(head),math.sin(head)])
        bridge=(2*u**3-3*u**2+1)*end+(u**3-2*u**2+u)*d0+(-2*u**3+3*u**2)*q+(u**3-u**2)*d1
        guide=np.vstack([guide,bridge[1:]])
        join_length=float(np.linalg.norm(np.diff(guide,axis=0),axis=1).sum())
        seen={target};key=target;start=join
        for _ in range(100):
            line=line_for(key)
            tail=np.array([line.interpolate(float(s)).coords[0][:2] for s in np.r_[np.arange(start+.5,line.length,.5),line.length]])
            guide=np.vstack([guide,tail]);end=np.asarray(line.coords[-1])[:2];head=tangent(line,end)
            nxt=([k for k,edges in g.edges.items() if edges.get(key)=='forward' and k not in seen] if reverse else [k for k,r in g.edges.get(key,{}).items() if r=='forward' and k not in seen])
            if not nxt:break
            key=min(nxt,key=lambda k:abs(angle_diff(tangent(line_for(k),np.asarray(line_for(k).coords[0])[:2]),head)))
            seen.add(key);start=0
            if np.linalg.norm(np.diff(guide,axis=0),axis=1).sum()>max(distance or 40,40)+30:break
    # If there is no destination lane, keep a visibly synthetic motion path.
    if len(guide)<2 or (target is None and not turn and action not in ('lane_change_left','lane_change_right','select_lane')):
        length=distance or (3 if action=='stop' else 25)
        guide=p0+np.linspace(0,length,max(2,int(length*4)))[:,None]*f
    ds=np.linalg.norm(np.diff(guide,axis=0),axis=1);guide=guide[np.r_[True,ds>1e-5]]
    s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(guide,axis=0),axis=1))]
    if distance is not None:length=min(distance,max(.1,s[-1]-2)) if target else min(distance,s[-1])
    elif turn or action in ('lane_change_left','lane_change_right','select_lane'):
        length=min(s[-1],join_length+5.)
    else:length=min(s[-1],max(25.,join_length+5.))
    # Simple bounded-speed time sampling; free mode does not claim dynamic feasibility.
    v=min(4.,st.get('target_speed_mps') or 4.);duration=max(2.,length/max(v,.1));n=int(math.ceil(duration/.1))
    stop=bool(st.get('stop_at_end') or action=='stop' or length<(distance or 0)-.1)
    u=np.linspace(0,1,n+1);progress=length*((3*u*u-2*u*u*u) if stop else (2*u*u-u*u*u))
    points=np.column_stack([np.interp(progress,s,guide[:,i]) for i in range(2)])
    speed=np.r_[np.linalg.norm(np.diff(points,axis=0),axis=1)/.1,0. if stop else length/(n*.1)]
    local=(points-initial[:2])@rot
    row={'index':0,'action':action,'source_clause':st['source_clause'],'status':'completed_offline','start_point':0,'end_point':len(points)-1,'trajectory_source':'free_mode_geometric_recovery','target':target,'target_reversed':bool(reverse),'reason':'Forced connection to a visible map road; normal road connectivity was bypassed.','checks_overridden':True,'warning':'Free-mode geometric recovery: road boundaries, lane direction and steering may be violated.','requested_distance_m':distance,'traveled_distance_m':float(np.linalg.norm(np.diff(points,axis=0),axis=1).sum()),'final_speed_mps':float(speed[-1]),'stop_at_end':stop}
    if distance is not None and length<distance-.1:row.update(stopped_at_road_end=True,reason=f'Requested {distance:g} m; stopped after {length:.1f} m at the available road end.')
    return {'scene':scene,'status':'completed_offline','stages':[row],'points':local.tolist(),'speed_mps':speed.tolist(),'dt':.1}

def execute_free(scene,plan,initial_state=None):
    if plan.get('status')!='parsed' or plan.get('unresolved_text'):return finite(scene,plan,initial_state,mode='free')
    _,initial,_=context(scene)
    state=copy.deepcopy(initial_state) if initial_state is not None else {'xy':[0.,0.],'heading':0.,'speed':float(np.linalg.norm(initial[7:9]))}
    points=[state['xy']];speeds=[state['speed']];rows=[];headings=[state['heading']]
    eligible={'go_straight','keep_lane','turn_left','turn_right','lane_change_left','lane_change_right','select_lane','u_turn','resume','slow_down','speed_up'}
    speed_target=state.get('target_speed_mps')
    for i,stage in enumerate(plan['stages']):
        stage=dict(stage)
        if i+1<len(plan['stages']):stage['next_action']=plan['stages'][i+1]['action']
        if stage['action'] in ('continuous_drive','resume') and i==len(plan['stages'])-1 and stage['trigger'] in ('now','after_previous') and not stage.get('target_text') and not stage.get('constraints'):
            rows.append({'index':i,'action':stage['action'],'source_clause':stage['source_clause'],'status':'completed_offline','start_point':len(points)-1,'end_point':len(points)-1,'reason':'Continue along connected map roads after the preceding maneuver.'})
            if stage.get('target_speed_mps') is not None:speed_target=stage['target_speed_mps']
            continue
        if stage['action']=='set_speed' and stage['trigger'] in ('now','after_previous') and not stage.get('target_text') and not stage.get('constraints') and stage.get('target_speed_mps') is not None:
            speed_target=stage['target_speed_mps']
            if not 0<=speed_target<=15:raise ValueError('Speed outside demo limits')
            rows.append({'index':i,'action':'set_speed','source_clause':stage['source_clause'],'status':'completed_offline','start_point':len(points)-1,'end_point':len(points)-1,'target_speed_mps':speed_target,'reason':'Speed target applied to subsequent driving.'})
            continue
        if speed_target is not None and stage.get('target_speed_mps') is None:stage['target_speed_mps']=speed_target
        if stage['action'] in ('lane_change_left','lane_change_right','select_lane') and i+1<len(plan['stages']):
            next_distance=plan['stages'][i+1].get('travel_distance_m')
            if next_distance is not None and next_distance<=20:stage['target_speed_mps']=min(stage.get('target_speed_mps') or 2.5,2.5)
        if stage['action'] in ('turn_left','turn_right','u_turn') and i+1<len(plan['stages']) and plan['stages'][i+1].get('travel_distance_m') is not None and plan['stages'][i+1]['travel_distance_m']<=20:stage['exit_speed_mps']=2.5
        one={**plan,'stages':[stage]}
        if stage['action'] in ('stop','hold_stopped','emergency_stop','cancel') and (state['speed']<.05 or stage['action'] in ('emergency_stop','cancel','hold_stopped')) and not stage.get('target_text') and not stage.get('constraints') and stage['trigger'] in ('now','after_previous'):
            r={'status':'completed_offline','points':[state['xy'],state['xy']],'speed_mps':[0.,0.],'heading_rad':[state['heading'],state['heading']],'dt':.1,'stages':[{'action':stage['action'],'source_clause':stage['source_clause'],'status':'completed_offline','start_point':0,'end_point':1,'traveled_distance_m':0.,'final_speed_mps':0.,'reason':'Stopped at the current position; no extra movement.'}]}
        elif stage['action'] in ('turn_left','turn_right','u_turn'):
            from navigation_turn_v15 import execute_turn
            r=execute_turn(scene,stage,state)
            if stage['action']=='u_turn' and r['status']!='completed_offline':
                from navigation_turn_v15 import road_available
                r=finite(scene,one,state,mode='safe' if road_available(scene,state) else 'free')
            if r['status']!='completed_offline' and not stage.get('constraints') and not stage.get('target_text') and not stage.get('completion_text') and stage.get('trigger') in ('now','after_previous','intersection') and stage.get('trigger_value') in (None,1):
                from road_end_recovery_v17 import at_road_end
                recovery=at_road_end(scene,stage,state)
                if recovery:r=recovery
        elif stage['action']=='go_straight' and stage.get('travel_distance_m') is None:
            from navigation_turn_v15 import execute_turn
            r=execute_turn(scene,stage,state)
            if r['status']!='completed_offline':
                r=finite(scene,one,state,mode='free')
                for row in r.get('stages',[]):
                    row['instruction_followed']=False
                    row['reason']='No connected straight-ahead exit found in the loaded map; following the available road bend instead. Straight-ahead instruction was not fulfilled.'
        elif stage['action'] in ('reverse','reverse_continuous'):
            from reverse_motion_v13 import execute_reverse
            r=execute_reverse(scene,stage,state)
        elif stage['action'] in ('pull_over','park'):
            from basic_maneuvers_v14 import roadside_stop
            r=roadside_stop(scene,stage,state)
        else:
            from navigation_turn_v15 import road_available
            r=finite(scene,one,state,mode='safe' if stage['action']=='u_turn' and road_available(scene,state) else 'free')
        if r['status']=='completed_offline' and stage['action']=='go_straight' and len(r['points'])>2:
            delta=np.asarray(r['points'][-1])-r['points'][0]
            if np.linalg.norm(delta)>2 and abs(angle_diff(math.atan2(delta[1],delta[0]),state['heading']))>math.radians(45) and not __import__('navigation_turn_v15').road_available(scene,state):
                r=recover(scene,stage,state)
        if r['status']=='completed_offline' and stage['action']=='u_turn' and not any(x.get('target') for x in r.get('stages',[])):
            r=recover(scene,stage,state)
        # Recover geometric failures, never unknown targets, visual conditions or invalid inputs.
        reason=' '.join(x.get('reason','') for x in r.get('stages',[]))
        forbidden=('Needs ','Explicit completion','Distance must','speed must','Multiple relative','no specified completion')
        if r['status']!='completed_offline' and stage['action'] in eligible and stage['trigger'] in ('now','after_previous') and not stage.get('constraints') and not stage.get('completion_text') and not any(x in reason for x in forbidden) and not __import__('navigation_turn_v15').road_available(scene,state):
            r=recover(scene,stage,state)
        # Retain actual speed across route replacements; time each forward maneuver
        # against the same acceleration/curvature policy instead of restarting it.
        if r['status']=='completed_offline' and stage['action'] in ('go_straight','keep_lane','lane_change_left','lane_change_right','select_lane','turn_left','turn_right','u_turn') and len(r['points'])>2:
            from route_speed_v18 import sample
            old=np.asarray(r['points']);oldarc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(old,axis=0),axis=1))]
            stopped=bool(stage.get('stop_at_end') or any(x.get('stopped_at_road_end') for x in r.get('stages',[])))
            qq,vv=sample(old,stage.get('target_speed_mps') or state.get('target_speed_mps') or 20/3.6,state['speed'],stopped,end_speed=stage.get('exit_speed_mps'))
            newarc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(qq,axis=0),axis=1))]
            for row in r.get('stages',[]):
                row['start_point']=int(np.argmin(abs(newarc-oldarc[min(row.get('start_point',0),len(old)-1)])))
                row['end_point']=int(np.argmin(abs(newarc-oldarc[min(row.get('end_point',len(old)-1),len(old)-1)])))
                row['final_speed_mps']=float(vv[row['end_point']])
            r['points']=qq.tolist();r['speed_mps']=vv.tolist();r.pop('heading_rad',None)
        offset=len(points)-1
        for row in r.get('stages',[]):
            row=dict(row);row.update(index=i,start_point=row.get('start_point',0)+offset,end_point=row.get('end_point',0)+offset);rows.append(row)
        if r['status']!='completed_offline':return {'scene':scene,'status':r['status'] if not i else 'partial','stages':rows,'points':points,'speed_mps':speeds,'heading_rad':headings,'dt':.1}
        pp=r['points'];points.extend(pp[1:]);speeds.extend(r['speed_mps'][1:]);heading=state['heading']
        for prior in reversed(pp[:-1]):
            d=np.asarray(pp[-1])-prior
            if np.linalg.norm(d)>.01:heading=float(math.atan2(d[1],d[0]));break
        stage_head=r.get('heading_rad')
        if stage_head:heading=stage_head[-1]
        else:stage_head=[state['heading']]+[float(math.atan2(b[1]-a[1],b[0]-a[0])) if np.linalg.norm(np.asarray(b)-a)>1e-5 else heading for a,b in zip(pp[:-1],pp[1:])]
        headings.extend(stage_head[1:])
        history=state.get('history',[])
        if r.get('is_reverse') and history:
            k=min(range(len(history)),key=lambda j:float(np.linalg.norm(np.asarray(history[j])-pp[-1])));history=history[:k+1]+[pp[-1]]
        else:history=history+pp
        state={'history':history,'xy':pp[-1],'heading':heading,'speed':r['speed_mps'][-1],**({'view_bounds':state['view_bounds']} if 'view_bounds' in state else {})}
    return {'scene':scene,'status':'completed_offline','stages':rows,'points':points,'speed_mps':speeds,'dt':.1,'mode':'free','target_speed_mps':speed_target,'heading_rad':headings}
