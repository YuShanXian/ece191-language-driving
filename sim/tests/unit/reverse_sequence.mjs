import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {runInteraction} from './interaction_runner.mjs';
const {PlannerWorker}=createRequire(import.meta.url)('../../worker-client.cjs');
const worker=new PlannerWorker({script:fileURLToPath(new URL('../../worker.py',import.meta.url))});
const reports=[];
try{
 for(const actions of [['reverse','reverse'],['reverse','u_turn']]){
  const r=await runInteraction(worker,{name:actions.join('-'),scene:1,latency:.03,inputs:actions.map((action,i)=>({at:i*9,action}))});
  reports.push(r);await writeFile(new URL('../results/reverse-sequence.json',import.meta.url),JSON.stringify(reports));console.log(r.spec.name,r.outcomes.map(x=>x.status),r.findings);
  assert.equal(r.findings.length,0);assert(r.outcomes.every(x=>x.status==='completed'));
  if(actions[1]==='reverse')assert(r.state.xy[0]<-19.8);
 }
 const old=JSON.parse(await readFile(new URL('../results/random-before/191042.json',import.meta.url)));
 const r=await runInteraction(worker,old.spec);reports.push(r);
 console.log('seed191042',r.outcomes.map(x=>x.status),r.findings);assert.equal(r.findings.length,0);
 await writeFile(new URL('../results/reverse-sequence.json',import.meta.url),JSON.stringify(reports));
}finally{worker.close();}
