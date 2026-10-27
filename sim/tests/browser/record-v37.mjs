// Use the production queue and vehicle with a virtual wall clock. Planner
// answers are delayed independently while physical integration keeps running.
import {Vehicle,angleDiff} from '../../web/motion.js';
import {Pipeline,directStage} from '../../web/pipeline.js';
export function rng(seed){return ()=>{seed|=0;seed=seed+0x6D2B79F5|0;let t=Math.imul(seed^seed>>>15,1|seed);t^=t+Math.imul(t^t>>>7,61|t);return ((t^t>>>14)>>>0)/4294967296;};}
export async function runInteraction(worker,spec,onFrame=()=>{}){
 const v=new Vehicle(),events=[],jobs=[],requests=[],findings=[],motion_samples=[];
 let time=0,next=0,sequence=0,idleSince=null;const random=rng(spec.seed||1);
 if(spec.state){v.reset(structuredClone(spec.state));v.history=structuredClone(spec.state.history||[spec.state.xy]);}
 const q=new Pipeline(v,request=>new Promise((resolve,reject)=>{
  jobs.push({id:++sequence,request:structuredClone(request),resolve,reject,issued:time,
   delay:spec.latency??[0,.03,.2,.8,2.5][Math.floor(random()*5)]});
 }),e=>{
  const event=structuredClone({...e,sim_time:time});events.push(event);
  if(e.type==='error')findings.push({kind:'execution_error',event});
  if(e.type==='completed'&&e.journey){
   const turns=e.journey.observed_movements.filter(m=>m.action!=='go_straight'&&!m.road_bend);
   if(turns.some(m=>m.action!==e.action||m.connector!==e.route_source))
    findings.push({kind:'unrequested_turn',event});
   if(e.execution?.expected_finish&&Math.hypot(...v.pose.xy.map((x,i)=>x-e.execution.expected_finish.xy[i]))>.4)
    findings.push({kind:'wrong_completion_position',event});
   if(e.phases?.length>1&&e.phases.slice(0,-1).some(p=>p.finish.speed>.02))
    findings.push({kind:'moving_gear_change',event});
  }
 });q.scene=spec.scene||1;
 const actions=spec.inputs;
 for(;time<(spec.limit||Math.max(180,(actions.at(-1)?.at||0)+180));time+=.05){
  while(next<actions.length&&actions[next].at<=time+.00001){
   const input=actions[next++];events.push({type:'test_input',sim_time:time,input});
   if(input.action==='cancel')q.cancel();
   else if(input.action==='pause')v.paused=true;
   else if(input.action==='play')v.paused=false;
   else q.add([input.stage||directStage(input.action)],{replace:input.replace||false,timeout:input.timeout||20});
  }
  q.tick(.05);
  for(const job of jobs.filter(j=>!j.planned)){
   job.planned=true;
   try{job.response=await worker.request(job.request);requests.push({id:job.id,time:job.issued,request:job.request,response:job.response});
    if(job.response.status==='ready'){
     const probe=new Vehicle();probe.reset(job.request.state);
     const route=job.response.phases?.[0]?.route||job.response.route;
     if(!probe.install(route))findings.push({kind:'invalid_ready_route',request:job.id,state:job.request.state});
    }
   }
   catch(e){job.error=e;}
  }
  for(const job of jobs.filter(j=>j.planned&&!j.delivered&&time>=j.issued+j.delay)){
   job.delivered=true;if(job.error)job.reject(job.error);else job.resolve({...job.response,request_id:String(job.id)});
  }
  await Promise.resolve();await Promise.resolve();
  v.tick(.05);onFrame(time,v,q);
  motion_samples.push({time,xy:[...v.pose.xy],heading:v.pose.heading,node_id:v.pose.node_id,speed:v.speed,
   stage_id:q.current?.id,action:q.current?.stage.action,status:q.current?.status,
   reverse:!!v.route?.reverse,distance:v.distance,epoch:v.epoch});
  if(v.jumps){findings.push({kind:'position_jump',time,state:v.state()});break;}
  if(v.maxHeadingStep>.36){findings.push({kind:'heading_jump',time,value:v.maxHeadingStep});break;}
  if(next===actions.length&&!q.current){
   idleSince??=time;
   const last=q.rows.at(-1);
   const extra=(v.route?.movements||[]).find(m=>v.distance>=m.start&&v.distance<m.end&&
    m.action!=='go_straight'&&!m.road_bend&&m.connector!==last?.routeSource);
   if(extra){findings.push({kind:'unrequested_continuation_turn',time,movement:extra});break;}
   if(time-idleSince>=(spec.afterCompletionSeconds??10))break;
  }else idleSince=null;
  if(next===actions.length&&q.blocked)break;
 }
 const outcomes=q.rows.map(r=>({id:r.id,action:r.stage.action,status:r.status,reason:r.reason,
   source:r.routeSource,attempts:r.attempts,request_id:r.requestId}));
 return {spec,simulated:time,moving_seconds:v.movingSeconds,distance:v.totalDistance,
  position_jumps:v.jumps,max_heading_step:v.maxHeadingStep,outcomes,findings,events,requests,motion_samples,state:v.state()};
}
