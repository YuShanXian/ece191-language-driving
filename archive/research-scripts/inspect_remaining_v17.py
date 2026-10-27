exec(open('historical-project/scripts/inspect_history_v17.py').read().split('for id in')[0])
rows=json.loads((r/'runs/project-v3/command-audit-v17/full-replay.json').read_text())
for row in rows:
 if row['status'] in ('completed_offline','live_control'):continue
 d=Path(row['path'].replace('D:\\','historical-drive/').replace('\\','/'));st=json.loads((d/'start-state.json').read_text());p=c[:2]+np.asarray(st['xy'])@rot.T;h=c[6]+st['heading'];key=locate(g,p,h)
 print(d.name,row['instruction'],'key',key,'state',st['xy'],flush=True)
 if key:
  n=g.nodes[key];s=n.baseline.project(Point(p));print('  remaining',n.baseline.length-s,'edges',g.edges.get(key),flush=True)
