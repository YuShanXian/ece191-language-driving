// Usage: node tests/replay_case.mjs results/random/191042.json
import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {runInteraction} from './interaction_runner.mjs';
if(!process.argv[2])throw Error('Provide a saved interaction JSON file');
const saved=JSON.parse(await readFile(process.argv[2],'utf8'));
const {PlannerWorker}=createRequire(import.meta.url)('../../worker-client.cjs');
const worker=new PlannerWorker({script:fileURLToPath(new URL('./cached_worker.py',import.meta.url))});
try{
 const r=await runInteraction(worker,saved.spec||saved);
 await writeFile(process.argv[2]+'.replayed.json',JSON.stringify(r));
 console.log(JSON.stringify({spec:r.spec,outcomes:r.outcomes,findings:r.findings},null,2));
 process.exitCode=r.findings.length?1:r.outcomes.some(x=>!['completed','applied','cancelled'].includes(x.status))?2:0;
}finally{worker.close();}
