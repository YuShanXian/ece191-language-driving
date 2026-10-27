import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {Vehicle} from '../../web/motion.js';
import {Pipeline,directStage} from '../../web/pipeline.js';
const {PlannerWorker}=createRequire(import.meta.url)('../../worker-client.cjs');
const worker=new PlannerWorker({script:fileURLToPath(new URL('../../worker.py',import.meta.url))});
const results=[];
try{
 for(const action of ['turn_right','u_turn']){
  const f=JSON.parse(await readFile(new URL(`../results/${action}-failed.json`,import.meta.url)));
  const v=new Vehicle();v.reset(f.request.state);v.history=f.request.state.history;
  const events=[],q=new Pipeline(v,r=>worker.request(r),e=>events.push(structuredClone(e)));
  q.add([directStage(action),directStage('stop')]);
  let elapsed=0;
  while(q.current&&elapsed<180){
   q.tick(.05);if(q.pending)while(q.pending)await new Promise(r=>setTimeout(r,5));
   if(q.blocked)break;v.tick(.05);elapsed+=.05;
  }
  const result={action,elapsed,rows:q.rows,events,position_jumps:v.jumps,state:v.state()};
  results.push(result);
  console.log(action,elapsed,q.rows.map(x=>x.status),events.filter(e=>['route_installed','completed','error','phase_completed'].includes(e.type)).map(e=>({type:e.type,xy:e.state.xy,phase:e.phase,reverse:e.reverse})),v.jumps);
  if(q.rows.some(x=>!['completed','applied'].includes(x.status))||v.jumps)process.exitCode=1;
 }
 await writeFile(new URL('../results/user-integration.json',import.meta.url),JSON.stringify(results,null,2));
}finally{worker.close();}
