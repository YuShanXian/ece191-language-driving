import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {Vehicle} from '../../web/motion.js';
import {Pipeline,directStage} from '../../web/pipeline.js';
const require=createRequire(import.meta.url);
const {PlannerWorker}=require('../../worker-client.cjs');
const worker=new PlannerWorker({script:fileURLToPath(new URL('../../worker.py',import.meta.url))});
const vehicle=new Vehicle(), events=[];
const pipeline=new Pipeline(vehicle,r=>worker.request(r),e=>{
 events.push(JSON.parse(JSON.stringify(e)));
 if(['completed','timed_out','error','blocked','route_installed'].includes(e.type))console.log(e.type,e.action,e.reason||'',JSON.stringify(e.state.xy));
});
const stages=['go_straight','lane_change_right','lane_change_left','go_straight','reverse','reverse','turn_left','lane_change_left','lane_change_right','go_straight','turn_left','reverse','turn_right'].map(directStage);
stages[4].travel_distance_m=200;
stages[5].travel_distance_m=2;
stages[11].travel_distance_m=80;
pipeline.add(stages);
let simulated=0;
try{
 while(pipeline.current && simulated<1200){
  pipeline.tick(.05);
  if(pipeline.pending){while(pipeline.pending)await new Promise(r=>setTimeout(r,5));}
  if(pipeline.blocked)break;
  vehicle.tick(.05);simulated+=.05;
 }
 const result={simulated,moving_seconds:vehicle.movingSeconds,position_jumps:vehicle.jumps,ended:vehicle.ended,route_remaining:vehicle.route.length-vehicle.distance,rows:pipeline.rows,events};
 await writeFile(new URL('../results/integration-sequence.json',import.meta.url),JSON.stringify(result,null,2));
 console.log('RESULT',simulated,vehicle.movingSeconds,pipeline.rows.map(r=>r.status));
 if(pipeline.rows.some(r=>r.status!=='completed')||vehicle.jumps||vehicle.movingSeconds<300)process.exitCode=1;
}finally{worker.close();}
