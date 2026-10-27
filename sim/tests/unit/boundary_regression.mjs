import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {runInteraction} from './interaction_runner.mjs';
const {PlannerWorker}=createRequire(import.meta.url)('../../worker-client.cjs');
const worker=new PlannerWorker({script:fileURLToPath(new URL('./cached_worker.py',import.meta.url))});
try{
 const r=await runInteraction(worker,{name:'reverse-map-boundary-then-straight',scene:4,seed:3740,latency:.2,
  inputs:[{at:0,action:'reverse',timeout:5},{at:.31,action:'go_straight'}]});
 await writeFile(new URL('../results/reverse-map-boundary-then-straight.json',import.meta.url),JSON.stringify(r));
 assert.deepEqual(r.findings,[]);
 assert.deepEqual(r.outcomes.map(o=>o.status),['timed_out','completed']);
 const timeout=r.events.find(e=>e.type==='timed_out');assert(Math.hypot(...timeout.state.xy)<.01);
 assert.match(timeout.reason,/Only 4\.2 m/);console.log(r.spec.name,r.outcomes.map(o=>o.status));
}finally{worker.close();}
