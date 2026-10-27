exec(open('historical-project/scripts/inspect20.py').read().split('for n in g.nodes.values():')[0])
for k in ['L63380','L63379']:
 n=g.nodes[k];print(k,'length',n.baseline.length,g.edges[k])
 for nk,rel in g.edges[k].items():
  other=g.nodes[nk];print(nk,rel,'angle',math.degrees(angle_diff(tangent(other.baseline,other.baseline.coords[-1]),tangent(n.baseline,n.baseline.coords[-1]))),'start',other.baseline.coords[0],'end',other.baseline.coords[-1])
