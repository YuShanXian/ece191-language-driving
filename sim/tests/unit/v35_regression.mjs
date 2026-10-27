import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {runInteraction} from './interaction_runner.mjs';
import {directStage} from '../../web/pipeline.js';
const {PlannerWorker}=createRequire(import.meta.url)('../../worker-client.cjs');
const worker=new PlannerWorker({script:fileURLToPath(new URL('./cached_worker.py',import.meta.url))});
const reports=[];
async function run(spec,expected){
 const r=await runInteraction(worker,spec);
 await writeFile(new URL('../results/'+spec.name+'.json',import.meta.url),JSON.stringify(r));
 assert.deepEqual(r.findings,[],spec.name);
 assert.deepEqual(r.outcomes.map(o=>o.status),expected||spec.inputs.map(()=> 'completed'),spec.name);
 reports.push({name:spec.name,outcomes:r.outcomes,moving_seconds:r.moving_seconds});
 console.log(spec.name,r.outcomes.map(o=>o.status+':'+o.source).join(','));return r;
}
try{
 for(let scene=1;scene<=7;scene++){
  const r=await run({name:`straight-scene${scene}`,scene,inputs:[{at:0,action:'go_straight'}]});
  if(scene===1)assert.equal(r.outcomes[0].source,'J_L63477_L67723');
  if(scene===5)assert.equal(r.outcomes[0].source,'J_L67707_L67757');
 }
 const fixture=JSON.parse(await readFile(new URL('../results/user-stop-fixture.json',import.meta.url)));
 const bent=await run({name:'user-stop-straight',scene:1,state:fixture.request.state,inputs:[{at:0,action:'go_straight'}]});
 assert.equal(bent.outcomes[0].source,'C64857');
 const journey=bent.events.find(e=>e.type==='completed').journey;
 assert(journey.observed_movements.some(m=>m.connector==='C64857'&&m.road_bend));
 assert(!journey.observed_movements.some(m=>m.action==='u_turn'));
 await run({name:'user-stop-wait-then-straight',scene:1,state:fixture.request.state,
  inputs:[{at:0,action:'lane_change_left',timeout:1},{at:0,action:'go_straight'}]},['timed_out','completed']);
 // Idempotence: selecting the current extreme must not fabricate movement.
 const current=await worker.request({...fixture.request,stage:directStage('leftmost_lane')});
 assert.equal(current.status,'control');assert.match(current.reason,/Already in the requested lane/);
 await run({name:'extreme-lanes',scene:1,inputs:['go_straight','rightmost_lane','leftmost_lane','leftmost_lane'].map(action=>({at:0,action}))},['completed','completed','completed','applied']);
 const main=['go_straight','rightmost_lane','leftmost_lane','go_straight','reverse','reverse','turn_left','lane_change_left','lane_change_right','go_straight','turn_left','reverse','turn_right'];
 const inputs=main.map((action,i)=>({at:0,action,stage:action==='reverse'?{...directStage(action),travel_distance_m:{4:200,5:2,11:80}[i]}:undefined}));
 await run({name:'main-preview',scene:1,limit:650,latency:.03,inputs});
}finally{
 worker.close();await writeFile(new URL('../results/v35-regression.json',import.meta.url),JSON.stringify(reports,null,2));
}
