import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {runInteraction,rng} from './interaction_runner.mjs';
import {directStage} from '../../web/pipeline.js';
const {PlannerWorker}=createRequire(import.meta.url)('../../worker-client.cjs');
const worker=new PlannerWorker({script:fileURLToPath(new URL('./cached_worker.py',import.meta.url))});
const read=async p=>JSON.parse(await readFile(new URL(p,import.meta.url),'utf8'));
const reports=[];
async function run(spec,expected){
 const r=await runInteraction(worker,spec);
 await writeFile(new URL('../results/'+spec.name+'.json',import.meta.url),JSON.stringify(r));
 console.log(spec.name, r.simulated.toFixed(2),r.outcomes.map(o=>o.status+':'+o.source).join(','),r.findings.map(x=>x.kind));
 reports.push({name:spec.name,outcomes:r.outcomes,findings:r.findings.map(x=>x.kind)});
 assert.deepEqual(r.findings,[],spec.name);
 if(expected)assert.deepEqual(r.outcomes.map(o=>o.status),expected,spec.name);
 return r;
}
const complete=n=>Array(n).fill('completed');
try{
 for(const id of [5,12,'bend']){
  const f=await read(`../results/reverse-${id}-fixture.json`);
  await run({name:`reverse-review-${id}`,scene:1,state:f.state,seed:3700+Number(id||0),latency:.2,
   afterCompletionSeconds:.5,inputs:[{at:0,stage:f.stage}]},complete(1));
 }
 await run({name:'two-consecutive-reverses',scene:1,seed:3710,inputs:[{at:0,action:'reverse'},{at:3.7,action:'reverse'}]},complete(2));
 await run({name:'reverse-unavailable-then-forward',scene:1,latency:.03,inputs:[
  {at:0,stage:{...directStage('reverse'),travel_distance_m:10000},timeout:1},
  {at:.31,stage:{...directStage('keep_lane'),travel_distance_m:5,stop_at_end:true}}
 ]},['timed_out','completed']);
 for(let scene=1;scene<=7;scene++){
  const r=await run({name:`straight-scene${scene}`,scene,latency:.03,inputs:[{at:0,action:'go_straight'}]},complete(1));
  if(scene===1)assert.equal(r.outcomes[0].source,'J_L63477_L67723');
  if(scene===5)assert.equal(r.outcomes[0].source,'J_L67707_L67757');
 }
 for(const file of ['user-stop-straight','user-stop-wait-then-straight','extreme-lanes']){
  const old=await read(`../results/historical-v35/${file}.json`);
  await run({...old.spec,name:file},old.outcomes.map(x=>x.status));
 }
 await run({name:'right-after-straight',scene:1,inputs:[{at:0,action:'go_straight'},{at:4.1,action:'turn_right'}]},complete(2));
 const main=['go_straight','lane_change_right','lane_change_left','reverse','reverse'];
 await run({name:'browser-preview',scene:1,latency:.03,afterCompletionSeconds:1,
  inputs:main.map((action,i)=>({at:[0,4.17,9.31,14.23,23.11][i],action}))},complete(5));
 // Retain the original eight-step / minimal recovery fixtures.
 for(const [version,file] of [['v34','user-replay-after.json']]){
  try{const old=await read(`../../refactor-${version}/results/${file}`);
   await run({...old.spec,name:`retained-${file.replace('.json','')}`},old.outcomes.map(x=>x.status));
  }catch(e){if(e.code==='ENOENT')console.log('fixture-path-missing',file);else throw e;}
 }
 await mkdir(new URL('../results/random/',import.meta.url),{recursive:true});
 for(let seed=37101;seed<=37112;seed++){
  const random=rng(seed);let at=0;
  const choices=['go_straight','lane_change_left','lane_change_right','reverse','turn_right','cancel'];
  const inputs=Array.from({length:6},(_,i)=>{at+=i?1+random()*8:0;return {at:+at.toFixed(3),action:choices[Math.floor(random()*choices.length)],replace:random()<.25,timeout:[1,5,20][Math.floor(random()*3)]};});
  await run({name:`random/${seed}`,scene:seed%7+1,seed,limit:160,inputs});
 }
}finally{worker.close();await writeFile(new URL('../results/regression-summary.json',import.meta.url),JSON.stringify(reports,null,2));}
