import {readFile,readdir,writeFile} from 'node:fs/promises';
import {Vehicle,Route,angleDiff} from '../../web/motion.js';
const dir=new URL('../results/random/',import.meta.url),findings=[];
for(const file of await readdir(dir)){
 const r=JSON.parse(await readFile(new URL(file,dir)));
 for(const q of r.requests){
  if(q.response.status!=='ready')continue;
  const v=new Vehicle();v.reset(q.request.state);const route=q.response.phases?.[0]?.route||q.response.route;
  if(v.install(route))continue;
  const path=new Route(route),origin=path.at(0),state=q.request.state;
  findings.push({seed:r.spec.seed,scene:r.spec.scene,action:q.request.stage.action,request_id:q.id,
   origin:state.xy,source:route.geometry_source,initial_heading_error:angleDiff(origin.heading,state.heading),
   start_error:Math.hypot(...origin.xy.map((x,i)=>x-state.xy[i])),length:path.length});
 }
}
await writeFile(new URL('../results/ready-contract-findings.json',import.meta.url),JSON.stringify(findings,null,2));
console.log('INVALID_READY',findings.length,findings);
