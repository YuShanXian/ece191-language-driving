import {readFile,writeFile,readdir,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import path from 'node:path';
const root=fileURLToPath(new URL('../',import.meta.url)),base=path.dirname(root.replace(/[\\/]$/,''));
const out=path.join(base,'review-data-full'),catalog=[],checks=[];
await mkdir(path.join(out,'cases'),{recursive:true});
const hash=s=>createHash('sha256').update(s).digest('hex');
const terminal=new Set(['completed','applied','timed_out','blocked','error','unsupported','cancelled','skipped']);
const cleanEvent=e=>Object.fromEntries(['type','stage_id','action','reason','request_id','route_source','phase','reverse','queue_mode','timeout'].filter(k=>e[k]!=null).map(k=>[k,e[k]]));
function summary(commands){const r={};for(const c of commands)r[c.status]=(r[c.status]||0)+1;return r;}
async function save(c){
 c.summary=summary(c.commands);c.duration=c.frames.at(-1)?.[0]||0;
 c.issue=Object.keys(c.summary).some(x=>!['completed','applied','cancelled','skipped'].includes(x))||!!c.findings?.length;
 await writeFile(path.join(out,'cases',c.id+'.json'),JSON.stringify(c));
 const {frames,events,commands,...small}=c;catalog.push({...small,commandCount:commands.length,actions:[...new Set(commands.map(x=>x.action))]});
}
// Browser runs retain measured checkpoints and recorded traveled-path samples.
// Their intermediate timing is explicitly interpolated, never called a video.
for(const version of ['v40']){
 const results=path.join(root,'results');let config;
 try{config=JSON.parse(await readFile(path.join(results,'browser-run-config.json'),'utf8'));}catch(e){if(version==='v40'&&e.code==='ENOENT')continue;throw e;}
 for(const [name,cfg] of Object.entries(config)){
  const logs=cfg.traceRoot||path.resolve(base,'../logs');
  const raw=await readFile(path.join(logs,'events.jsonl'),'utf8'),all=raw.trim().split('\n').map(JSON.parse);
  const start=Date.parse(cfg.start),end=Date.parse(cfg.end);
  let events=all.filter(e=>Date.parse(e.time)>=start&&Date.parse(e.time)<=end&&e.client_release===(cfg.client_release||version));
  const session=events.find(e=>e.type==='activated')?.session_id;if(!session)continue;
  events=events.filter(e=>e.session_id===session);const points=[],anchors=[],commands=new Map();
  for(const e of events){
   const t=(Date.parse(e.time)-start)/1000;
   if(e.type==='queued'){
    e.stages.forEach((s,i)=>commands.set(e.added_stage_ids[i],{id:e.added_stage_ids[i],label:s.source_clause,action:s.action,added:t,status:'queued'}));
    // These examples start from a reset scene. Retain the real parse wait at
    // the stationary initial pose instead of silently trimming it away.
    if(!anchors.length&&e.state?.speed===0){points.push({d:0,xy:e.state.xy,h:e.state.heading});anchors.push({t,d:0,state:e.state});}
   }
   if(e.type==='parsed'){} // Browser main cases may reserve a language slot first.
   if(e.stage_id!=null&&e.action&&e.action!=='parse'){
    if(!commands.has(e.stage_id))commands.set(e.stage_id,{id:e.stage_id,action:e.action,label:e.action.replaceAll('_',' '),added:t,status:'queued'});
    const c=commands.get(e.stage_id);c.action=e.action;if(e.type==='activated')c.started=t;
    if(terminal.has(e.type)){c.status=e.type;c.finished=t;c.reason=e.reason;}
    if(e.request_id){try{const request=JSON.parse(await readFile(path.join(logs,'requests',e.request_id+'.json'),'utf8'));c.label=request.request.stage.source_clause;}catch{}}
   }
   if(e.journey){
    const j=e.journey;points.push({d:j.start_distance,xy:j.origin.xy,h:j.origin.heading});
    for(const p of j.samples)points.push({d:j.start_distance+p.distance,xy:p.xy,h:p.heading});
    const last=j.samples.at(-1);let d=e.execution?e.execution.start_distance+e.execution.distance:j.start_distance+(last?.distance||0)+(last?Math.hypot(...e.state.xy.map((x,i)=>x-last.xy[i])):0);
    points.push({d,xy:e.state.xy,h:e.state.heading});anchors.push({t,d,state:e.state});
    const active=events.find(x=>x.type==='activated'&&x.stage_id===e.stage_id);
    if(active)anchors.push({t:(Date.parse(active.time)-start)/1000,d:j.start_distance,state:active.state});
   }
   if(e.type==='telemetry'){anchors.push({t,d:e.distance_m,state:e.state});points.push({d:e.distance_m,xy:e.state.xy,h:e.state.heading});}
  }
  for(const [id,c] of commands)if(c.action==='parse')commands.delete(id);
  const orderedCommands=[...commands.values()].sort((a,b)=>(a.started??a.added)-(b.started??b.added));
  assert.deepEqual(orderedCommands.filter(c=>terminal.has(c.status)).map(c=>[c.action,c.status]),cfg.expected,`${version} browser ${name}: instruction import differs from recorded acceptance`);
  points.sort((a,b)=>a.d-b.d);anchors.sort((a,b)=>a.t-b.t);
  const unique=(xs,key)=>xs.filter((x,i)=>i===xs.length-1||Math.abs(x[key]-xs[i+1][key])>1e-6);
  const line=unique(points,'d'),ticks=unique(anchors,'t');if(!ticks.length)continue;
  const frames=[];let a=0,p=0;
  const angle=(x,y,u)=>x+Math.atan2(Math.sin(y-x),Math.cos(y-x))*u;
  for(let t=ticks[0].t;t<=ticks.at(-1).t+.0001;t+=.1){
   while(a<ticks.length-2&&ticks[a+1].t<t)a++;
   const x=ticks[a],y=ticks[Math.min(a+1,ticks.length-1)],u=Math.max(0,Math.min(1,(t-x.t)/Math.max(.001,y.t-x.t))),d=x.d+(y.d-x.d)*u;
   while(p<line.length-2&&line[p+1].d<d)p++;
   const l=line[p],r=line[Math.min(p+1,line.length-1)],v=Math.max(0,Math.min(1,(d-l.d)/Math.max(1e-8,r.d-l.d)));
   const current=[...commands.values()].find(c=>c.started!=null&&c.started<=t&&(c.finished==null||c.finished>t));
   const stateEvent=events.filter(e=>e.stage_id===current?.id&&['activated','route_installed','executing','waiting','braking_reverse','braking_maneuver','phase_completed'].includes(e.type)&&(Date.parse(e.time)-start)/1000<=t).at(-1);
   const phase=({activated:'planning',route_installed:'approaching',phase_completed:'transition'})[stateEvent?.type]||stateEvent?.type||'active';
   frames.push([+t.toFixed(3),l.xy[0]+v*(r.xy[0]-l.xy[0]),l.xy[1]+v*(r.xy[1]-l.xy[1]),angle(l.h,r.h,v),x.state.speed+(y.state.speed-x.state.speed)*u,current?.id??null,current?phase:'continuation',current?.action.startsWith('reverse')||false]);
  }
  const id=`${version}-browser-${name}`;
  await save({id,title:cfg.title||({main:'Right turn — automatic road continuation',preview:'Right-turn continuation — isolated browser verification',user_failure:'Original v38 failure — stopped after right turn, straight timed out'})[name]||name,version,scene:cfg.scene||1,kind:'browser',
   fidelity:'Recorded browser checkpoints and traveled path; position and timing between samples are interpolated. This is not a video.',
   source:{path:path.join(results,'browser-run-config.json'),sha256:hash(JSON.stringify(cfg)),session},recordedAt:cfg.start,
   commands:orderedCommands,events:events.map(e=>({...cleanEvent(e),t:(Date.parse(e.time)-start)/1000})).filter(e=>e.type!=='telemetry'),frames,findings:cfg.findings||[],replayVerified:false});
 }
}
catalog.sort((a,b)=>(a.practice?1:0)-(b.practice?1:0)||b.version.localeCompare(a.version)||a.kind.localeCompare(b.kind)||a.title.localeCompare(b.title));
await writeFile(path.join(out,'catalog.json'),JSON.stringify({schema:1,builtAt:new Date().toISOString(),cases:catalog}));
await writeFile(path.join(root,'results/review-import-checks.json'),JSON.stringify(checks,null,2));
console.log(JSON.stringify({cases:catalog.length,browser:catalog.filter(c=>c.kind==='browser').length,simulations:checks.filter(x=>x.passed).length,reconstructionFailures:checks.filter(x=>!x.passed)}));
if(checks.some(x=>!x.passed&&!['user-replay-after.json','user-replay-before.json'].includes(x.source)))process.exitCode=1;
