import {createRequire} from 'node:module';
import {mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {runInteraction,rng} from './interaction_runner.mjs';
const {PlannerWorker}=createRequire(import.meta.url)('../../worker-client.cjs');
const worker=new PlannerWorker({script:fileURLToPath(new URL('./cached_worker.py',import.meta.url))});
const positional=process.argv.slice(2).filter(x=>/^\d+$/.test(x));
const count=Number(positional[0]||70),firstSeed=Number(positional[1]||191000),reports=[];
if(!Number.isSafeInteger(count)||count<1||count>10000)throw Error('Choose 1 to 10000 sessions');
const actions=['go_straight','turn_left','turn_right','lane_change_left','lane_change_right','u_turn','reverse'];
const out=new URL('../results/random/',import.meta.url);await mkdir(out,{recursive:true});
try{
 for(let n=0;n<count;n++){
  const seed=firstSeed+n,random=rng(seed);let t=0;const inputs=[];
  for(let j=0;j<8;j++){
   const action=j>0&&random()<.18?'cancel':actions[Math.floor(random()*actions.length)];
   inputs.push({at:t,action,replace:random()<.2,timeout:[5,10,20][Math.floor(random()*3)]});
   t+=[.1,.4,1,3,5,8,12][Math.floor(random()*7)];
  }
  const spec={name:'random-'+seed,seed,scene:((seed-191000)%7+7)%7+1,inputs};
  const result=await runInteraction(worker,spec);
  const unresolved=result.outcomes.filter(o=>!['completed','applied','cancelled'].includes(o.status));
  const report={seed,scene:spec.scene,inputs,simulated:result.simulated,moving_seconds:result.moving_seconds,
   findings:result.findings.map(f=>f.kind),outcomes:result.outcomes,
   unresolved:unresolved.length};
  reports.push(report);
  await writeFile(new URL(seed+'.json',out),JSON.stringify(result));
  await writeFile(new URL('../results/random-summary.json',import.meta.url),JSON.stringify(reports,null,2));
  console.log(seed,'scene',spec.scene,'findings',report.findings.join(','),'outcomes',result.outcomes.map(o=>o.status).join(','));
 }
 const coverage={sessions:reports.length,clicks:reports.length*8,scenes:7,
  contract_failure_sessions:reports.filter(r=>r.findings.length).length,
  unresolved_sessions:reports.filter(r=>r.unresolved).length,
  unresolved_instructions:reports.reduce((n,r)=>n+r.unresolved,0),
  all_commands_verified:reports.every(r=>!r.findings.length&&!r.unresolved),
  note:'Exploration is not acceptance. No witness means unresolved, never impossible or successful.'};
 await writeFile(new URL('../results/random-coverage.json',import.meta.url),JSON.stringify(coverage,null,2));
 console.log('TOTAL',JSON.stringify(coverage));
 if(reports.some(r=>r.findings.length))process.exitCode=1;
 else if(coverage.unresolved_sessions&&!process.argv.includes('--explore'))process.exitCode=2;
}finally{worker.close();}
