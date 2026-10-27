import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {runInteraction} from './interaction_runner.mjs';
const {PlannerWorker}=createRequire(import.meta.url)('../../worker-client.cjs');
const worker=new PlannerWorker({script:fileURLToPath(new URL('./cached_worker.py',import.meta.url))});
try{
 const minimized=JSON.parse(await readFile(new URL('../results/historical-v34/minimized-user-sequence.json',import.meta.url)));
 const base=minimized.spec,origin=base.inputs[0].at;
 for(const delta of [0,-.2,.2,-1,1]){
  const spec={...base,name:'three-click-timing-'+delta,inputs:base.inputs.map((x,i)=>({...x,at:x.at-origin+(i?delta:0)}))};
  const r=await runInteraction(worker,spec);
  await writeFile(new URL('../results/'+spec.name+'.json',import.meta.url),JSON.stringify(r));
  console.log(spec.name,r.outcomes.map(x=>x.status),r.findings.map(x=>x.kind));
  assert.deepEqual(r.findings,[]);assert(r.outcomes.every(x=>x.status==='completed'));
 }
 const r=await runInteraction(worker,{name:'ordinary-reverse-then-recovery',scene:1,latency:.2,inputs:[{at:0,action:'reverse'},{at:4.43,action:'u_turn'}]});
 await writeFile(new URL('../results/ordinary-reverse-then-recovery.json',import.meta.url),JSON.stringify(r));
 console.log(r.spec.name,r.outcomes.map(x=>x.status),r.findings.map(x=>x.kind));
 assert.deepEqual(r.findings,[]);assert(r.outcomes.every(x=>x.status==='completed'));
}finally{worker.close();}
