import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {runInteraction} from './interaction_runner.mjs';
const {PlannerWorker}=createRequire(import.meta.url)('../../worker-client.cjs');
const worker=new PlannerWorker({script:fileURLToPath(new URL('./cached_worker.py',import.meta.url))});
const summary=[];
async function run(spec,expected){
 const r=await runInteraction(worker,spec);
 await writeFile(new URL(`../results/${spec.name}.json`,import.meta.url),JSON.stringify(r));
 assert.deepEqual(r.findings,[],spec.name);
 assert.deepEqual(r.outcomes.map(x=>x.status),expected,spec.name);
 summary.push({name:spec.name,outcomes:r.outcomes,findings:r.findings});
 console.log(spec.name,r.outcomes.map(x=>x.status+':'+x.source).join(','));return r;
}
try {
 const request=JSON.parse(await readFile(new URL('../results/user-right-request.json',import.meta.url)));
 const stopped=JSON.parse(await readFile(new URL('../results/user-straight-request.json',import.meta.url)));
 // No second command may be necessary to leave the 19 cm lane.
 for(const delay of [.03,.8,2.5]){
  const r=await run({name:`right-tail-${delay}`,scene:1,seed:3901,latency:delay,state:request.request.state,
   inputs:[{at:0,stage:request.request.stage}],afterCompletionSeconds:14},['completed']);
  const done=r.events.find(e=>e.type==='completed');
  const tail=r.motion_samples.filter(p=>p.time>done.sim_time+.1 && p.time<done.sim_time+10);
  assert(tail.some(p=>p.node_id==='C69782'),'native continuation never reached');
  assert(tail.every(p=>p.speed>.05),'unrequested stop after right turn');
  assert(r.distance-done.journey.start_distance-done.execution.distance>25,'insufficient movement after right turn');
  assert.equal(r.outcomes[0].source,'C70254');
 }
 await run({name:'straight-from-user-stop',scene:1,state:stopped.request.state,latency:.03,
  inputs:[{at:0,stage:stopped.request.stage}],afterCompletionSeconds:5},['completed']);
 for(let scene=1;scene<=7;scene++){
  const r=await run({name:`straight-scene${scene}`,scene,latency:.03,inputs:[{at:0,action:'go_straight'}]},['completed']);
  if(scene===1)assert.equal(r.outcomes[0].source,'J_L63477_L67723');
  if(scene===5)assert.equal(r.outcomes[0].source,'J_L67707_L67757');
 }
 const actions=['go_straight','lane_change_right','lane_change_left','turn_right','reverse'];
 // These changes finish beyond the right exit. Retain its timeout and prove
 // that the later reverse still executes; never relabel it as a success.
 await run({name:'right-request-after-passing-exit',scene:1,latency:.1,
  inputs:actions.map((action,i)=>({at:i*.7,action})),afterCompletionSeconds:1},['completed','completed','completed','timed_out','completed']);
 await run({name:'browser-route-preview',scene:1,latency:.1,
  inputs:[{at:0,action:'go_straight'},{at:.7,action:'turn_right'},{at:29,action:'go_straight'}],afterCompletionSeconds:15},Array(3).fill('completed'));
 for(const name of ['user-stop-straight','user-stop-wait-then-straight','extreme-lanes']){
  const old=JSON.parse(await readFile(new URL(`../results/historical-v35/${name}.json`,import.meta.url)));
  await run({...old.spec,name},old.outcomes.map(x=>x.status));
 }
 for(const name of ['two-consecutive-reverses','reverse-unavailable-then-forward','reverse-review-5','reverse-review-12','reverse-review-bend']){
  const old=JSON.parse(await readFile(new URL(`../results/historical-v37/${name}.json`,import.meta.url)));
  await run({...old.spec,name},old.outcomes.map(x=>x.status));
 }
} finally {worker.close();await writeFile(new URL('../results/regression-summary.json',import.meta.url),JSON.stringify(summary,null,2));}
