exec(open('historical-project/scripts/inspect20.py').read().split("for n in g.nodes.values():")[0])
for k in ['C70134','C69292','C68639']:
 n=g.nodes[k];a=np.asarray(n.baseline.coords);print(k,'start/end',*(round(math.degrees(angle_diff(tangent(n.baseline,x),h)),1) for x in [a[0],a[-1]]))
import json
rows=[json.loads(l) for l in open('historical-project/runs/project-v3/recording-demo-v1/command-history.jsonl')];rows=[r for r in rows if r.get('status')=='received' and r.get('id') in ['ui-1792575941373','ui-1792575942858','ui-1792575976876','ui-1792575978479']]
for r in rows:
 st=r['state'];p=c[:2]+np.array(st['xy'])@rot.T;h=c[6]+st['heading'];k=locate(g,p,h);print(r['id'],k, g.nodes[k].baseline.project(Point(p)),g.edges[k])
