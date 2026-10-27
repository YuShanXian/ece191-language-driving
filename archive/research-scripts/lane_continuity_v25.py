"""Local lane correspondence, independent of downstream route length."""
import math
import numpy as np
from trajectory_checks import tangent,angle_diff

def connection_geometry(source,target):
 a=np.asarray(source.baseline.coords[-1])[:2];b=np.asarray(target.baseline.coords[0])[:2]
 h0=tangent(source.baseline,a);h1=tangent(target.baseline,b)
 turn=angle_diff(h1,h0);mid=h0+turn/2
 # Remove lateral displacement explained by a gently curving road.
 lateral=float((b-a)@np.array([-math.sin(mid),math.cos(mid)]))
 return turn,lateral

def lane_rank_error(source,target,groups):
 turn,_=connection_geometry(source,target)
 si=source.lane_index or 1;ti=target.lane_index or 1
 if turn<math.radians(-30):
  si=max(n.lane_index or 1 for n in groups[source.lane_group])-si
  ti=max(n.lane_index or 1 for n in groups[target.lane_group])-ti
 return abs(si-ti)

def forward_choices(g,key):
 node=g.nodes[key];choices=[n for n,r in g.edges.get(key,{}).items() if r=='forward']
 if node.kind!='lane':return sorted(choices)
 candidates=[]
 for nk in choices:
  nxt=g.nodes[nk]
  exits=[g.nodes[k] for k,r in g.edges.get(nk,{}).items() if r=='forward' and g.nodes[k].kind=='lane'] if nxt.kind=='connector' else [nxt]
  if not exits:continue
  target=exits[0];turn,lateral=connection_geometry(node,target)
  ordinal=abs((node.lane_index or 1)-(target.lane_index or 1))
  candidates.append((nk,abs(turn),abs(lateral),ordinal))
 straight=[c for c in candidates if c[1]<math.radians(30)]
 if straight:
  nearest=min(c[2] for c in straight)
  # Geometry is creatoritative when road blocks renumber lanes. Use the lane
  # ordinal only between exits lying within half a lane of the closest match.
  aligned=[c for c in straight if c[2]<=nearest+1.5]
  return [c[0] for c in sorted(aligned,key=lambda c:(c[3],c[2],c[1],c[0]))]
 if not candidates:return []
 smallest=min(c[1] for c in candidates)
 aligned=[c for c in candidates if c[1]<=smallest+math.radians(15)]
 return [c[0] for c in sorted(aligned,key=lambda c:(c[3],c[1],c[2],c[0]))]
