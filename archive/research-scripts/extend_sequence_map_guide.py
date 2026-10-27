from mtr_project.paths import ROOT
p=ROOT/'scripts/execute_language_plan_v2.py';s=p.read_text(encoding='utf-8-sig');s=s.replace('center=np.load(ROOT/', 'center=np.load(ROOT/').replace("['center'].copy();initial=", "['center'].astype(float).copy();initial=")
# Extend only uniquely connected road geometry so short exit lanes do not force a premature stop.
s=s.replace("  v0=float(np.linalg.norm(center[7:9]))", "  completion_key=keys[-1]\n  for _ in range(3):\n   if sum(graph.nodes[k].baseline.length for k in keys)>90:break\n   nxt=[k for k,r in graph.edges.get(keys[-1],{}).items() if r=='forward' and k not in keys]\n   if len(nxt)!=1:break\n   keys=keys+nxt\n  v0=float(np.linalg.norm(center[7:9]))")
s=s.replace("endnode=graph.nodes[keys[-1]]", "endnode=graph.nodes[completion_key]")
p.write_text(s)
