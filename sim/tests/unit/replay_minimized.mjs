import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {runInteraction} from './interaction_runner.mjs';
const {PlannerWorker}=createRequire(import.meta.url)('../../worker-client.cjs');
const worker=new PlannerWorker({script:fileURLToPath(new URL('../../worker.py',import.meta.url))});
const minimized=JSON.parse(await readFile(new URL('../results/minimized-user-sequence.json',import.meta.url)));
const base=minimized.spec,origin=base.inputs[0].at,results=[];
try{
 for(const delta of [0,-.2,.2,-1,1]){
  const spec={...base,name:'three-click-timing-'+delta,inputs:base.inputs.map((x,i)=>({...x,at:x.at-origin+(i?delta:0)}))};
  const r=await runInteraction(worker,spec);results.push({delta,...r});
  console.log('THREE_CLICK',delta,r.outcomes.map(x=>x.status),r.findings.map(x=>x.kind));
  if(r.outcomes.some(x=>x.status!=='completed')||r.findings.length)process.exitCode=1;
 }
 await writeFile(new URL('../results/minimized-timing-regression.json',import.meta.url),JSON.stringify(results));
}finally{worker.close();}
