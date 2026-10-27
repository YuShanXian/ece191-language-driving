import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {runInteraction} from './interaction_runner.mjs';
const {PlannerWorker}=createRequire(import.meta.url)('../../worker-client.cjs');
const worker=new PlannerWorker({script:fileURLToPath(new URL('../../worker.py',import.meta.url))});
const original=JSON.parse(await readFile(new URL('../results/user-replay-before.json',import.meta.url)));
let spec=original.spec,trials=0;const history=[];
function reproduces(r){return r.outcomes.at(-1)?.action==='u_turn'&&r.outcomes.at(-1).status==='timed_out'&&r.state.node_id==='L67748';}
try{
 for(let size=Math.floor(spec.inputs.length/2);size>=1;size=Math.floor(size/2)){
  let changed=true;
  while(changed&&trials<30){
   changed=false;
   for(let i=0;i<spec.inputs.length-1&&trials<30;i+=size){
    const inputs=spec.inputs.filter((_,j)=>j<i||j>=i+size||j===spec.inputs.length-1);
    const candidate={...spec,name:'minimized-user-regression',inputs};
    const r=await runInteraction(worker,candidate);trials++;
    const kept=reproduces(r);history.push({trial:trials,removed:[i,size],remaining:inputs.length,reproduces:kept});
    if(kept){spec=candidate;changed=true;console.log('REDUCED',inputs.length,'inputs',trials);break;}
   }
  }
 }
 await writeFile(new URL('../results/minimized-user-sequence.json',import.meta.url),JSON.stringify({spec,trials,history,criterion:'Final U-turn times out at L67748; a separate full-footprint witness proves it feasible.'},null,2));
 console.log('MINIMIZED',original.spec.inputs.length,'to',spec.inputs.length,'inputs',trials,'trials');
}finally{worker.close();}
