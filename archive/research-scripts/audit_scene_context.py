"""Map-only turn-context audit of all 13 frozen windows; future is diagnostic only."""
import heapq
import json
import pickle
import sqlite3
from collections import Counter
from datetime import datetime, timezone
import numpy as np
from shapely.geometry import Point
from nuplan.common.maps.maps_datatypes import LaneConnectorType
from evaluate_candidate_checks import load_graph
from trajectory_checks import tangent, angle_diff
from mtr_project.paths import ROOT, sha256, write_json


def metadata(map_path):
    with sqlite3.connect(map_path.as_uri()+'?mode=ro', uri=True) as conn:
        rows = conn.execute('SELECT fid,exit_lane_fid,entry_lane_fid,turn_type_fid FROM lane_connectors ORDER BY fid').fetchall()
    result, edges = {}, {}
    for fid, upstream, downstream, raw_type in rows:
        key = 'C'+str(fid)
        try: kind = LaneConnectorType(raw_type).name
        except (ValueError, TypeError): kind = 'UNRECOGNIZED'
        result[key] = {'type': kind, 'upstream': 'L'+str(upstream), 'downstream': 'L'+str(downstream)}
        edges.setdefault('L'+str(upstream), []).append(key)
        edges.setdefault(key, []).append('L'+str(downstream))
    return result, edges


def forward_search(graph, start, xy, connector_info, global_edges, maximum_distance):
    if start not in graph.nodes:
        return {'connectors': [], 'missing_nodes': [start], 'reached_nodes': []}
    progress = graph.nodes[start].baseline.project(Point(xy))
    queue = [(-progress, start, [start])]
    visited = {}; turns = []; missing = []
    while queue:
        distance, key, route = heapq.heappop(queue)
        if key in visited and visited[key] <= distance: continue
        visited[key] = distance
        node = graph.nodes[key]
        if key.startswith('C'):
            info = connector_info.get(key, {'type':'UNRECOGNIZED'})
            turns.append({'connector': key, 'turn_type': info['type'],
                          'distance_to_entry_m': max(0., float(distance)),
                          'distance_to_exit_m': float(distance+node.baseline.length),
                          'already_occupied': key == start, 'path': route, 'raw_map_turn_type': info.get('raw_map_turn_type', info['type']), 'baseline_heading_change_deg': info.get('baseline_heading_change_deg')})
        # Stop at the first non-straight connector: a right turn after a left is not a right-turn option here.
        if key.startswith('C') and connector_info.get(key, {}).get('type') != 'STRAIGHT': continue
        next_distance = distance + node.baseline.length
        if next_distance > maximum_distance: continue
        for nxt in global_edges.get(key, []):
            if nxt not in graph.nodes:
                missing.append({'from':key, 'to':nxt, 'distance_m':float(next_distance)})
            elif nxt not in route:
                heapq.heappush(queue, (next_distance, nxt, route+[nxt]))
    return {'connectors': sorted(turns, key=lambda r:(r['distance_to_entry_m'], r['connector'])),
            'missing_nodes': missing, 'reached_nodes': sorted(visited), 'entry_distances_m': visited}


def adjacent_starts(graph, start, xy, heading):
    if start not in graph.nodes or graph.nodes[start].kind != 'lane': return []
    visited={start}; pending=[start]; neighbors=[]
    while pending:
        current=pending.pop()
        for nxt, relation in graph.edges.get(current, {}).items():
            if relation not in ('left','right') or nxt in visited: continue
            visited.add(nxt)
            node=graph.nodes[nxt]
            if node.baseline.distance(Point(xy)) <= 15 and abs(angle_diff(tangent(node.baseline,xy),heading)) <= np.pi/3:
                pending.append(nxt); neighbors.append(nxt)
    return sorted(neighbors)


def classify(direct, adjacent, current, near_distance, actual_heading, future_matched):
    if current is None: return 'unresolved_current_lane'
    direct_turns=[r for r in direct['connectors'] if r['turn_type'] in ('LEFT','RIGHT','UTURN')]
    side_turns=[r for data in adjacent for r in data['search']['connectors'] if r['turn_type'] in ('LEFT','RIGHT','UTURN')]
    if any(r['already_occupied'] or r['distance_to_entry_m']<=near_distance for r in direct_turns):
        return 'near_turn_from_current_lane'
    if any(r['distance_to_entry_m']<=near_distance for r in side_turns):
        return 'near_turn_requires_adjacent_lane'
    if direct_turns or side_turns: return 'turn_farther_ahead'
    if direct['missing_nodes'] or any(r['search']['missing_nodes'] for r in adjacent): return 'unresolved_map_frontier'
    if any(r['turn_type'] not in ('STRAIGHT',) for data in [direct]+[r['search'] for r in adjacent] for r in data['connectors']):
        return 'unresolved_connector_type'
    if abs(actual_heading)>=30 or not future_matched: return 'unresolved_recorded_motion'
    return 'straight_control_in_audited_range'


def draw_window(graph, ego, row, destination):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    heading=float(ego['heading'][20]); origin=ego['position'][20,:2]
    rotation=np.array([[np.cos(heading),-np.sin(heading)],[np.sin(heading),np.cos(heading)]])
    def local(points): return (np.asarray(points)[...,:2]-origin)@rotation
    fig,ax=plt.subplots(figsize=(9,7))
    for node in graph.nodes.values():
        points=local(node.baseline.coords)
        ax.plot(points[:,0],points[:,1],color='#cbd2d9',lw=.7,zorder=0)
    colors={'LEFT':'#a750a3','RIGHT':'#148d76','UTURN':'#bd7135','STRAIGHT':'#b8c9df'}
    seen=set()
    for source, data in [('current',row['direct'])]+[('adjacent',r['search']) for r in row['adjacent']]:
        for connector in data['connectors']:
            key=connector['connector']
            if key in seen: continue
            seen.add(key)
            node=graph.nodes[key]; points=local(node.baseline.coords)
            color=colors.get(connector['turn_type'],'#666666')
            ax.plot(points[:,0],points[:,1],color=color,lw=2,ls='-' if source=='current' else ':')
            if connector['turn_type'] in ('LEFT','RIGHT','UTURN'):
                middle=local([node.baseline.interpolate(.5,normalized=True).coords[0]])[0]
                if -30<middle[0]<170 and abs(middle[1])<100:
                    ax.annotate(key+' '+connector['turn_type']+'\n'+str(round(connector['distance_to_entry_m']))+' m',middle,fontsize=7,color=color)
    if row['current_node'] in graph.nodes:
        points=local(graph.nodes[row['current_node']].baseline.coords)
        ax.plot(points[:,0],points[:,1],color='#d4a226',lw=3,label='Current lane/connector')
    history=local(ego['position'][:21]);future=local(ego['position'][20:81])
    ax.plot(history[:,0],history[:,1],color='#252f3b',lw=2,label='Recorded history')
    ax.plot(future[:,0],future[:,1],'--',color='#c94640',lw=2,label='Recorded future (evaluation only)')
    ax.scatter(0,0,color='black',s=35,zorder=5)
    ax.set_xlim(-30,170);ax.set_ylim(-100,100);ax.set_aspect('equal');ax.grid(alpha=.15)
    ax.set_xlabel('Forward from current heading (m)');ax.set_ylabel('Left (m)')
    ax.set_title(row['key']+' | '+row['classification']+'\n'+f"speed {row['speed_mps']:.1f} m/s; 6s travel at current speed {row['constant_speed_6s_m']:.1f} m; observed heading change {row['recorded_heading_change_deg']:.1f} deg",fontsize=10)
    ax.legend(loc='lower left',fontsize=8)
    fig.text(.03,.025,'Purple = geometric LEFT; green = RIGHT; dotted = hypothetical adjacent-lane access.\nTopology is not permission, arrival-time prediction, or execution feasibility. View may crop distant branches.',fontsize=8)
    fig.tight_layout(rect=[0,.07,1,1]);fig.savefig(destination/(row['key']+'.png'),dpi=150);plt.close(fig)


def main():
    source=ROOT/'runs/project-v2/turn-challenge-v1/evaluation.json'
    evaluation=json.loads(source.read_text())
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination=ROOT/'runs/project-v3/scene-context'/stamp
    destination.mkdir(parents=True,exist_ok=False)
    spec={'minimum_search_distance_along_baselines_m':150.,'actual_search_distance_rule':'max(150, near_threshold + 30)','near_distance_rule':'max(30 metres, 6 * current speed m/s)',
          'near_distance_scope':'Screening heuristic, NOT a reachable-time guarantee. 30m floor retains stopped vehicles near intersections.',
          'adjacent_lane_rule':'Lateral lane neighbors at current position or entry to any forward-reachable lane before the first turn; centerline distance <=15m and heading difference <=60deg. Hypothetical access only; no crossing legality or lane-change feasibility claim.',
          'turn_source':'Connector baseline endpoint tangent change: <30deg straight, >=150deg U-turn, otherwise signed left/right. Raw map enum retained separately because two near connectors have incompatible labels. Stop at first geometric turn. Forward topology from lane_connectors table, not MTR predictions.',
          'classification_scope':'Exploratory post-hoc stratification. Preserve all13 original windows. Do not compare subset success rates to the original denominator.',
          'future_scope':'Recorded future only diagnoses observed motion and matcher health; never used to generate online choices.'}
    write_json(destination/'specification.json',spec)
    sources={str(source.relative_to(ROOT)):sha256(source)}; results=[]; map_metadata={}
    for result in evaluation['windows']:
        window=result['window']; sample=ROOT/'samples'/window['sample']
        conv_path=sample/'conversion.json';conv=json.loads(conv_path.read_text());scenario_path=sample/conv['scenario']
        screen_path=ROOT/'runs'/window['run']/'anchored_feasibility.json'
        for p in [conv_path,scenario_path,screen_path]:
            name=str(p.relative_to(ROOT));digest=sha256(p)
            if evaluation['source_sha256'].get(name)!=digest: raise ValueError('Frozen source changed '+name)
            sources[name]=digest
        with scenario_path.open('rb') as stream: ego=pickle.load(stream)['tracks']['ego']['state']
        if not np.all(ego['valid'][:81]) or conv['current_timestamp_us']!=window['timestamp_us']:raise ValueError('Invalid ego anchor')
        map_path=ROOT/conv['source_map'];db=ROOT/conv['source_db']
        for p in [map_path,db]:
            name=str(p.relative_to(ROOT))
            if name not in sources:sources[name]=sha256(p)
        if str(map_path) not in map_metadata:map_metadata[str(map_path)]=metadata(map_path)
        connector_info,global_edges=map_metadata[str(map_path)]
        graph=load_graph(np.asarray(conv['origin_xy_m']),conv['source_epsg'],conv['source_map'])
        connector_info = {key:dict(value) for key,value in connector_info.items()}
        for key, info in connector_info.items():
            if key not in graph.nodes: continue
            baseline=graph.nodes[key].baseline
            change=float(np.degrees(angle_diff(tangent(baseline,baseline.coords[-1]),tangent(baseline,baseline.coords[0]))))
            info['raw_map_turn_type']=info['type']
            info['baseline_heading_change_deg']=change
            info['type']='STRAIGHT' if abs(change)<30 else ('UTURN' if abs(change)>=150 else ('LEFT' if change>0 else 'RIGHT'))
        history=graph.match(ego['position'][:21,:2],float(ego['heading'][0]))
        current=history['node_sequence'][-1] if history['matched'] else None
        saved=json.loads(screen_path.read_text())['summary']['past_only_start_node']
        if current!=saved:raise ValueError('Current lane does not reproduce')
        point=ego['position'][20,:2];heading=float(ego['heading'][20]);speed=float(conv['current_speed_mps'])
        future=graph.match(ego['position'][20:81,:2],heading,start_nodes={current}) if current else {'matched':False,'failure':'unresolved_current_lane'}
        body=graph.body_check(ego['position'][20:81,:2],heading,float(ego['length'][20]),float(ego['width'][20]))
        actual_heading=float(np.degrees(np.unwrap(ego['heading'][20:81].astype(float))[-1]-heading))
        near=max(30.,6*speed);radius=max(150.,near+30.)
        direct=forward_search(graph,current,point,connector_info,global_edges,radius)
        adjacent=[]
        # Also inspect lateral alternatives after leaving an already-occupied straight connector.
        for reached in direct['reached_nodes']:
            if graph.nodes[reached].kind != 'lane': continue
            transfer_point=point if reached==current else np.asarray(graph.nodes[reached].baseline.coords[0])
            transfer_heading=heading if reached==current else tangent(graph.nodes[reached].baseline,transfer_point)
            prefix=max(0.,direct['entry_distances_m'][reached])
            for node in adjacent_starts(graph,reached,transfer_point,transfer_heading):
                side=forward_search(graph,node,transfer_point,connector_info,global_edges,max(0.,radius-prefix))
                for connector in side['connectors']:
                    connector['distance_to_entry_m']+=prefix
                    connector['distance_to_exit_m']+=prefix
                    connector['already_occupied']=False
                adjacent.append({'start_node':node,'transfer_from_node':reached,'prefix_distance_m':prefix,'search':side})
        with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as conn:
            tags=conn.execute('SELECT DISTINCT s.type,p.timestamp FROM scenario_tag s JOIN lidar_pc p ON s.lidar_pc_record_id=p.record_id WHERE s.type LIKE ? ORDER BY p.timestamp',('%turn%',)).fetchall()
        tag_context={name:{'count_in_log':sum(t==name for t,ts in tags),'nearest_offset_seconds':min(((ts-window['timestamp_us'])/1e6 for t,ts in tags if t==name),key=abs)} for name in sorted({t for t,ts in tags})}
        row={'key':window['key'],'window':window,'current_node':current,'speed_mps':speed,'constant_speed_6s_m':6*speed,
             'near_threshold_m':near,'search_distance_m':radius,'direct':direct,'adjacent':adjacent,
             'recorded_heading_change_deg':actual_heading,'recorded_future_match':future,'recorded_future_body_check':body,'turn_tags':tag_context,
             'classification':classify(direct,adjacent,current,near,actual_heading,future['matched'])}
        results.append(row);draw_window(graph,ego,row,destination)
        write_json(destination/'audit.partial-progress.json',{'windows':results})
        print(json.dumps({'key':row['key'],'class':row['classification'],'current':current,'heading':round(actual_heading,1),
                          'direct_turns':[(c['connector'],c['turn_type'],round(c['distance_to_entry_m'],1)) for c in direct['connectors'] if c['turn_type']!='STRAIGHT'],
                          'adjacent_lanes':len(adjacent),'future_match':future['matched'],'body_pass':body['passed']},ensure_ascii=False),flush=True)
    summary={'windows':len(results),'class_counts':dict(Counter(r['classification'] for r in results)),
             'recorded_future_matches':sum(r['recorded_future_match']['matched'] for r in results),
             'recorded_future_body_passes':sum(r['recorded_future_body_check']['passed'] for r in results)}
    audit={'specification':spec,'summary':summary,'windows':results,'source_sha256':sources,
           'implementation_sha256':{p:sha256(ROOT/p) for p in ['scripts/audit_scene_context.py','scripts/evaluate_candidate_checks.py','scripts/trajectory_checks.py']}}
    write_json(destination/'audit.json',audit)
    write_json(destination/'cohorts.json',{'scope':spec['classification_scope'],
        'near_turn_current_lane':[r['window'] for r in results if r['classification']=='near_turn_from_current_lane'],
        'near_turn_requires_lane_change':[r['window'] for r in results if r['classification']=='near_turn_requires_adjacent_lane'],
        'farther_turn_context':[r['window'] for r in results if r['classification']=='turn_farther_ahead'],
        'straight_controls':[r['window'] for r in results if r['classification']=='straight_control_in_audited_range'],
        'unresolved':[r['window'] for r in results if r['classification'].startswith('unresolved')]})
    html=['<!doctype html><meta charset="utf-8"><title>13-window scene context audit</title><style>body{font:16px Arial;max-width:1100px;margin:40px auto;color:#243b50}img{width:100%}section{border-top:1px solid #ccd;padding:20px 0}pre{white-space:pre-wrap}</style><h1>13-window scene context audit</h1><p>Map topology and recorded motion; no candidate-success-based selection. Purple: left; green: right; dotted: hypothetical adjacent-lane access. Not a legal or execution guarantee.</p><pre>'+json.dumps(summary,indent=2)+'</pre>']
    for r in results:html+=['<section><h2>'+r['key']+'</h2><p>'+r['classification']+'</p><img src="'+r['key']+'.png"><pre>'+json.dumps({'current_node':r['current_node'],'near_threshold_m':r['near_threshold_m'],'turn_tags':r['turn_tags'],'recorded_future_match':{k:v for k,v in r['recorded_future_match'].items() if k not in ('node_sequence',)}},indent=2)+'</pre></section>']
    (destination/'index.html').write_text('\n'.join(html),encoding='utf-8')
    print(json.dumps({'output':str(destination),'summary':summary},indent=2))


if __name__=='__main__':main()

