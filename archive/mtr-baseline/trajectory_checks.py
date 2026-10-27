"""Offline, assumption-limited checks for experimental MTR candidates.

These checks are not a certified safety planner. No recorded future is used.
"""
from dataclasses import dataclass
from functools import lru_cache
import math
import numpy as np
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

@dataclass
class RoadNode:
    key: str
    polygon: object
    baseline: object
    kind: str
    lane_group: int | None = None
    lane_index: int | None = None

def angle_diff(a,b):
    return float(np.arctan2(np.sin(a-b),np.cos(a-b)))

def tangent(line, point):
    d=line.project(Point(point))
    p=np.asarray(line.interpolate(max(0,d-.5)).coords[0])[:2]
    q=np.asarray(line.interpolate(min(line.length,d+.5)).coords[0])[:2]
    return math.atan2(*(q-p)[::-1])

def headings(points, initial_heading, dt=.1):
    result=[float(initial_heading)]
    for i in range(1,len(points)):
        # Geometric tangent of a candidate curve; a trailing 0.5s chord lags turns.
        # Candidate points are forecasts, so looking at the next candidate point
        # does not expose a recorded future. Retain heading for low-speed jitter.
        if i<len(points)-1:d=(points[i+1]-points[i-1])/(2*dt)
        elif i>=2:
            d=(3*points[i]-4*points[i-1]+points[i-2])/(2*dt)
            if np.linalg.norm(points[i]-points[i-1])<=.5*dt:d=np.zeros(2)
        else:d=(points[i]-points[i-1])/dt
        result.append(float(math.atan2(d[1],d[0])) if np.linalg.norm(d)>.5 else result[-1])
    return np.asarray(result)

def footprint(xy,heading,length,width,margin=0):
    corners=np.array([[1,1],[1,-1],[-1,-1],[-1,1]],float)*[length/2+margin,width/2+margin]
    c,s=np.cos(heading),np.sin(heading)
    return Polygon(contact-removed([[c,s],[-s,c]])+xy)

class RoadGraph:
    def __init__(self,nodes,edges,tolerance=.05):
        self.nodes={n.key:n for n in nodes}
        self.keys=list(self.nodes)
        self.edges=edges
        self.tolerance=tolerance
        self.shapes=[n.polygon.buffer(tolerance) for n in self.nodes.values()]
        self.tree=STRtree(self.shapes)
        self.surface=unary_union([n.polygon for n in self.nodes.values()]).buffer(tolerance)

    @lru_cache(maxsize=32768)
    def paths(self,source,target):
        if source==target:return ((source,),)
        queue=[(source,)]
        found=[]
        # Up to 3 transitions between 0.1-second samples; geometry also checked.
        for _ in range(3):
            nextq=[]
            for path in queue:
                for nxt in self.edges.get(path[-1],{}):
                    if nxt in path:continue
                    p=path+(nxt,)
                    if nxt==target:found.append(p)
                    else:nextq.append(p)
            queue=nextq
        return tuple(found)

    @lru_cache(maxsize=32768)
    def corridor(self,path):
        return unary_union([self.nodes[k].polygon for k in path]).buffer(self.tolerance)

    @lru_cache(maxsize=2048)
    def forward_corridor(self,start):
        visited={start};frontier={start}
        for _ in range(10):
            nxt={b for a in frontier for b,r in self.edges.get(a,{}).items() if r=='forward'}-visited
            visited|=nxt;frontier=nxt
        return unary_union([self.nodes[k].polygon for k in visited]).buffer(self.tolerance)

    def settled_lane_changes(self,route,points,initial_heading,length,width):
        if not route.get('matched'):return
        angles=headings(points,initial_heading)
        for event in route['lane_changes']:
            target=self.forward_corridor(event['to'])
            enough_time=event['step']<=len(points)-6
            event['settled_for_last_half_second']=bool(enough_time and all(
                target.covers(footprint(p,h,length,width)) for p,h in zip(points[-6:],angles[-6:])))

    def match(self,points,initial_heading,dt=.1,start_nodes=None,return_end_states=False):
        points=np.asarray(points,float)
        angles=headings(points,initial_heading,dt)
        states={}
        for i,(xy,angle) in enumerate(zip(points,angles)):
            point=Point(xy)
            candidates=[]
            for idx in self.tree.query(point,predicate='intersects'):
                key=self.keys[int(idx)];node=self.nodes[key]
                if i==0 and start_nodes is not None and key not in start_nodes:continue
                if abs(angle_diff(angle,tangent(node.baseline,xy)))>np.radians(60):continue
                candidates.append((key,node.baseline.distance(point)))
            if not candidates:return {'matched':False,'failure':'outside_road_or_wrong_direction','failure_step':i}
            if i==0:
                states={k:(dist,[k],[]) for k,dist in candidates}
                continue
            new={}
            segment=LineString([points[i-1],xy])
            for nxt,dist in candidates:
                best=None
                for prior,(cost,sequence,events) in states.items():
                    for path in self.paths(prior,nxt):
                        if not self.corridor(path).covers(segment):continue
                        additions=[];penalty=0
                        for a,b in zip(path,path[1:]):
                            relation=self.edges[a][b]
                            penalty+=10 if relation in ('left','right') else .01
                            if relation in ('left','right'):
                                additions.append({'step':i,'action':'lane_change_'+relation,'from':a,'to':b})
                        score=cost+dist+penalty
                        if best is None or score<best[0]:best=(score,sequence+[nxt],events+additions)
                if best is not None:new[nxt]=best
            if not new:return {'matched':False,'failure':'disconnected_or_forbidden_direction','failure_step':i}
            states=new
        _,sequence,events=min(states.values(),key=lambda s:s[0])
        compact=[sequence[0]]
        for k in sequence[1:]:
            if k!=compact[-1]:compact.append(k)
        turn_events=[]
        for key in dict.fromkeys(sequence):
            n=self.nodes[key]
            if n.kind!='connector':continue
            idxs=[i for i,k in enumerate(sequence) if k==key]
            # Actual heading progress while on a connector, not its untraversed future.
            change=angle_diff(angles[idxs[-1]],angles[max(0,idxs[0]-1)])
            if abs(change)>=np.radians(30):
                turn_events.append({'action':'turn_left' if change>0 else 'turn_right',
                                    'connector':key,'heading_change_deg':np.degrees(change)})
        result = {'matched':True,'node_sequence':sequence,'route':compact,
                'lane_changes':events,'turns':turn_events,
                'ending_heading_deg':float(np.degrees(angles[-1]))}
        if return_end_states:
            result['viable_end_states'] = [{'node':key,'cost':float(value[0])} for key,value in sorted(states.items())]
        return result

    def body_check(self,points,initial_heading,length,width,dt=.1,diagnostics=False):
        angles=headings(points,initial_heading,dt)
        failed=[]
        outside_areas=[]
        # Check endpoints and midpoints; still a sampled approximation to swept volume.
        for i,(xy,a) in enumerate(zip(points,angles)):
            shape=footprint(xy,a,length,width)
            if not self.surface.covers(shape):failed.append(float(i))
            if diagnostics:outside_areas.append({'step':float(i),'outside_area_m2':float(shape.difference(self.surface).area)})
            if i:
                mid=(points[i-1]+xy)/2;midangle=angles[i-1]+angle_diff(a,angles[i-1])/2
                shape=footprint(mid,midangle,length,width)
                if not self.surface.covers(shape):failed.append(i-.5)
                if diagnostics:outside_areas.append({'step':i-.5,'outside_area_m2':float(shape.difference(self.surface).area)})
        result={'passed':not failed,'outside_sample_steps':failed}
        if diagnostics:
            result.update(max_outside_area_m2=max((r['outside_area_m2'] for r in outside_areas),default=0.),outside_area_samples=[r for r in outside_areas if r['outside_area_m2']>0],interpretation='Geometric map-boundary mismatch; not proof of unsafe driving. Strict pass threshold unchanged.')
        return result

def motion_check(points,initial_velocity,dt=.1,initial_acceleration=None):
    velocity=np.diff(points,axis=0)/dt
    acceleration=np.diff(np.vstack([initial_velocity,velocity]),axis=0)/dt
    jerk=np.diff(acceleration,axis=0)/dt
    if initial_acceleration is not None:jerk=np.diff(np.vstack([initial_acceleration,acceleration]),axis=0)/dt
    # Transparent fixed screening values, not tuned to make these samples pass.
    limits={'speed_mps':40.,'acceleration_mps2':8.,'jerk_mps3':25.}
    values={'speed_mps':float(np.linalg.norm(velocity,axis=1).max()),
            'acceleration_mps2':float(np.linalg.norm(acceleration,axis=1).max()),
            'jerk_mps3':float(np.linalg.norm(jerk,axis=1).max()) if len(jerk) else 0.}
    return {'passed':all(values[k]<=limits[k] for k in limits),'peaks':values,'limits':limits,
            'end_speed_mps':float(np.linalg.norm(velocity[-10:],axis=1).mean()),
            'end_max_speed_mps':float(np.linalg.norm(velocity[-10:],axis=1).max()),
            'max_displacement_m':float(np.linalg.norm(points-points[0],axis=1).max())}

def collision_check(points,initial_heading,length,width,obstacles,dt=.1):
    angles=headings(points,initial_heading,dt)
    hits=[]
    for i,(xy,a) in enumerate(zip(points,angles)):
        for fraction in ([0.] if i==0 else [-.5,0.]):
            time=(i+fraction)*dt
            p=xy if fraction==0 else (xy+points[i-1])/2
            h=a if fraction==0 else angles[i-1]+angle_diff(a,angles[i-1])/2
            ego=footprint(p,h,length,width,.2)
            for obj in obstacles:
                other_xy=np.asarray(obj['xy'])+np.asarray(obj['velocity'])*time
                if np.linalg.norm(p-other_xy)>length+obj['length']+2:continue
                if ego.intersects(footprint(other_xy,obj['heading'],obj['length'],obj['width'],.2)):
                    hits.append({'time_sec':time,'object_id':obj['id'],'category':obj['category']})
            if hits:return {'passed':False,'first_hits':hits}
    return {'passed':True,'first_hits':[]}
