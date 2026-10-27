import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {runInteraction} from './interaction_runner.mjs';
const {PlannerWorker}=createRequire(import.meta.url)('../../worker-client.cjs');
const baseline=process.argv.includes('--baseline');
const worker=new PlannerWorker({script:fileURLToPath(new URL(baseline?'../../worker.py':'../../worker.py',import.meta.url))});
const trace=JSON.parse(await readFile(new URL('../results/user-session.json',import.meta.url)));
const input=trace.filter(e=>e.type==='queued'||e.type==='cancelled'),start=Date.parse(input[0].time);
const inputs=input.map(e=>({at:(Date.parse(e.time)-start)/1000,action:e.type==='cancelled'?'cancel':e.stages[0].action,stage:e.stages?.[0],timeout:20}));
const spec={name:'user-eight-steps',seed:191,scene:1,latency:.015,inputs};
try{
 const r=await runInteraction(worker,spec);
 await writeFile(new URL(`../results/user-replay-${baseline?'before':'after'}.json`,import.meta.url),JSON.stringify(r,null,2));
 console.log('REPLAY',baseline?'v33':'v34',r.simulated,r.outcomes,r.findings.map(f=>f.kind));
 const expected=['cancelled','completed','cancelled','completed','cancelled','completed','timed_out',baseline?'timed_out':'completed'];
 if(JSON.stringify(r.outcomes.map(o=>o.status))!==JSON.stringify(expected)||r.findings.length)process.exitCode=1;
}finally{worker.close();}
