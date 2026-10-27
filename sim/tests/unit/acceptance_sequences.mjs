import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {Vehicle} from '../../web/motion.js';
import {Pipeline,directStage} from '../../web/pipeline.js';
const {PlannerWorker}=createRequire(import.meta.url)('../../worker-client.cjs');
const worker=new PlannerWorker({script:fileURLToPath(new URL('../../worker.py',import.meta.url))});
const results=[];
try{
 for(const actions of [['go_straight','turn_right','turn_right','stop'],['go_straight','go_straight','u_turn','go_straight','stop']]){
  const v=new Vehicle(),events=[],q=new Pipeline(v,r=>worker.request(r),e=>events.push(structuredClone(e)));
  q.add(actions.map(directStage));let elapsed=0;
  while(q.current&&elapsed<300){
   q.tick(.05);while(q.pending)await new Promise(r=>setTimeout(r,5));
   if(q.blocked)break;v.tick(.05);elapsed+=.05;
  }
  results.push({actions,elapsed,rows:q.rows,events,jumps:v.jumps,state:v.state()});
  console.log(actions,elapsed,q.rows.map(r=>({status:r.status,source:r.routeSource,reason:r.reason})),v.pose);
  if(q.rows.some(r=>!['completed','applied'].includes(r.status))||v.jumps)process.exitCode=1;
 }
 await writeFile(new URL('../results/acceptance-sequences.json',import.meta.url),JSON.stringify(results,null,2));
}finally{worker.close();}
