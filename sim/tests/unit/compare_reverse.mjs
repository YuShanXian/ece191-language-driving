import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import {runInteraction} from './interaction_runner.mjs';
const {PlannerWorker}=createRequire(import.meta.url)('../../worker-client.cjs');
const reports=[];
for(const [label,path] of [['current','./cached_worker.py']]){
 const worker=new PlannerWorker({script:fileURLToPath(new URL(path,import.meta.url))});
 try{
  const r=await runInteraction(worker,{name:'minimal-two-reverses',scene:1,latency:.03,
   inputs:[{at:0,action:'reverse'},{at:9,action:'reverse'}]});
  reports.push({label,...r});console.log(label,r.outcomes.map(x=>x.status),r.findings.map(x=>x.kind));
 {assert.equal(r.findings.length,0);assert(r.outcomes.every(x=>x.status==='completed'));}
 }finally{worker.close();}
}
await writeFile(new URL('../results/two-click-before-after.json',import.meta.url),JSON.stringify(reports));
