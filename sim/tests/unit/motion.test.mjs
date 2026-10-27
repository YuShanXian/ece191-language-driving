import test from 'node:test';
import assert from 'node:assert/strict';
import {Vehicle} from '../../web/motion.js';
import {Pipeline,directStage} from '../../web/pipeline.js';
const straight=(start=0,end=1000)=>({points:Array.from({length:Math.floor(end-start)+1},(_,i)=>[start+i,0]),segments:[{node_id:'L1',start:0,end:end-start}]});
const drive=(vehicle,pipeline,seconds)=>{for(let i=0;i<seconds*100;i++){vehicle.tick(.01);pipeline.tick(.01);}};

test('waiting after an internal maneuver brake resumes the connected neutral route',async()=>{
 const vehicle=new Vehicle();vehicle.install(straight());vehicle.target=0;
 const queue=new Pipeline(vehicle,async()=>({status:'waiting',route:straight(),reason:'next opportunity'}));
 queue.add([directStage('u_turn')]);queue.current.resumeTarget=4;queue.tick(.01);await Promise.resolve();
 drive(vehicle,queue,.5);assert.equal(vehicle.target,4);assert(vehicle.pose.xy[0]>.1);
 assert.equal(queue.current.status,'waiting');
});
test('three seconds of planner latency never pauses existing driving',async()=>{
 const vehicle=new Vehicle();vehicle.speed=5;assert.ok(vehicle.install(straight()));let resolve;
 const queue=new Pipeline(vehicle,()=>new Promise(r=>resolve=r));queue.add([directStage('go_straight')]);queue.tick(.01);
 const before=vehicle.pose.xy[0];drive(vehicle,queue,3);assert.ok(vehicle.pose.xy[0]-before>14);
 resolve({status:'ready',route:straight(),maneuver_start_m:20,completion_m:35});await Promise.resolve();
 assert.equal(queue.current.status,'approaching');assert.equal(vehicle.jumps,0);
 drive(vehicle,queue,6);assert.equal(queue.rows[0].status,'completed');assert.ok(vehicle.pose.xy[0]>40);
});
test('cancelling invalidates an in-flight route without moving the car',async()=>{
 const vehicle=new Vehicle();let resolve;const queue=new Pipeline(vehicle,()=>new Promise(r=>resolve=r));queue.add([directStage('turn_left')]);queue.tick(.01);queue.cancel();
 resolve({status:'ready',route:straight(),completion_m:10});await Promise.resolve();assert.equal(vehicle.route,null);assert.equal(queue.rows[0].status,'cancelled');
});
test('timeout records failure then executes later instructions in order without stopping',async()=>{
 const vehicle=new Vehicle();vehicle.install(straight());vehicle.speed=5;const queue=new Pipeline(vehicle,async()=>({status:'waiting',reason:'later',route:straight(),retry_after_m:100}));
 queue.add([directStage('turn_left'),directStage('speed_up'),directStage('slow_down')],{timeout:2});queue.tick(.01);await Promise.resolve();drive(vehicle,queue,3);
 assert.deepEqual(queue.rows.map(r=>r.status),['timed_out','applied','applied']);assert.equal(queue.current,undefined);assert.ok(vehicle.pose.xy[0]>14);
});

test('a route returned after timeout cannot replace the next step trajectory',async()=>{
 const vehicle=new Vehicle();vehicle.install(straight());vehicle.speed=5;let resolve;
 const queue=new Pipeline(vehicle,()=>new Promise(r=>resolve=r));
 queue.add([directStage('turn_left'),directStage('speed_up')],{timeout:1});queue.tick(.01);drive(vehicle,queue,2);
 assert.equal(queue.rows[0].status,'timed_out');assert.equal(queue.rows[1].status,'applied');
 const epoch=vehicle.epoch;resolve({status:'ready',route:straight(),maneuver_start_m:20,completion_m:35});await Promise.resolve();
 assert.equal(vehicle.epoch,epoch);assert.equal(queue.current,undefined);
});

test('a known maneuver approach longer than the waiting limit still completes',async()=>{
 const vehicle=new Vehicle();vehicle.install(straight());vehicle.speed=5;
 const queue=new Pipeline(vehicle,async()=>({status:'ready',route:straight(),maneuver_start_m:30,completion_m:45}));
 queue.add([directStage('go_straight'),directStage('speed_up')],{timeout:2});queue.tick(.01);await Promise.resolve();drive(vehicle,queue,10);
 assert.deepEqual(queue.rows.map(r=>r.status),['completed','applied']);assert.ok(queue.rows[0].execution.visited_nodes.includes('L1'));
});
test('reverse preempts only a held queue and preserves its remaining order',()=>{
 const vehicle=new Vehicle(),queue=new Pipeline(vehicle,async()=>({}));queue.add([directStage('go_straight'),directStage('turn_left')]);queue.current.status='blocked';queue.add([directStage('reverse')]);
 assert.deepEqual(queue.rows.map(r=>r.stage.action),['reverse','go_straight','turn_left']);queue.complete();assert.equal(queue.current.status,'blocked');
});
test('an unrelated route cannot snap the vehicle sideways or rotate it 90 degrees',()=>{
 const vehicle=new Vehicle();assert.equal(vehicle.install({points:[[0,0],[0,30]],segments:[]}),false);assert.equal(vehicle.install({points:[[0,4],[40,4]],segments:[]}),false);assert.deepEqual(vehicle.pose.xy,[0,0]);
});
test('pausing freezes both movement and the waiting clock',()=>{
 const vehicle=new Vehicle();vehicle.install(straight());const queue=new Pipeline(vehicle,()=>new Promise(()=>{}));queue.add([directStage('turn_left')]);queue.tick(.01);vehicle.paused=true;drive(vehicle,queue,5);assert.equal(queue.current.waited,0);assert.equal(vehicle.totalDistance,0);
});
test('cancelling removes the unexecuted trajectory so a speed change cannot replay it',()=>{
 const vehicle=new Vehicle();vehicle.install(straight());const queue=new Pipeline(vehicle,async()=>({}));queue.add([directStage('turn_left')]);queue.cancel();vehicle.target=10;drive(vehicle,queue,3);assert.deepEqual(vehicle.pose.xy,[0,0]);assert.equal(vehicle.route,null);
});
test('replace pending preserves the committed maneuver and replaces only later steps',()=>{
 const vehicle=new Vehicle(),queue=new Pipeline(vehicle,async()=>({}));queue.add([directStage('turn_left'),directStage('turn_right')]);queue.current.status='executing';queue.add([directStage('lane_change_left')],{replace:true});assert.deepEqual(queue.rows.map(r=>r.stage.action),['turn_left','lane_change_left']);assert.equal(queue.current.status,'executing');
});
test('reverse brakes to zero before requesting a backwards trajectory',async()=>{
 const vehicle=new Vehicle();vehicle.install(straight());vehicle.speed=5;let requestedSpeed=null;
 const queue=new Pipeline(vehicle,async request=>{requestedSpeed=request.state.speed;return {status:'blocked',reason:'test'};});
 queue.add([directStage('reverse')]);queue.tick(.01);assert.equal(queue.current.status,'braking_reverse');assert.equal(requestedSpeed,null);
 drive(vehicle,queue,3);await Promise.resolve();assert.ok(requestedSpeed<.02);assert.ok(vehicle.pose.xy[0]>4);assert.ok(vehicle.pose.xy[0]<6);
});
test('a slow language parser reserves order before later direct-button commands',()=>{
 const vehicle=new Vehicle();vehicle.install(straight());vehicle.speed=5;let calls=0;const queue=new Pipeline(vehicle,async()=>{calls++;return {};});
 const reserved=queue.reserveLanguage('left then right',{timeout:20});queue.add([directStage('go_straight')]);drive(vehicle,queue,3);
 assert.equal(calls,0);assert.ok(vehicle.totalDistance>14);
 queue.resolveLanguage(reserved,{status:'parsed',stages:[directStage('turn_left'),directStage('turn_right')]});
 assert.deepEqual(queue.rows.map(r=>r.stage.action),['turn_left','turn_right','go_straight']);
});
test('a cancelled language response cannot restart the vehicle',()=>{
 const vehicle=new Vehicle(),queue=new Pipeline(vehicle,async()=>({}));
 const reserved=queue.reserveLanguage('left',{timeout:20});queue.cancel();
 assert.equal(queue.resolveLanguage(reserved,{status:'parsed',stages:[directStage('turn_left')]}),false);
 assert.equal(queue.current,undefined);assert.equal(vehicle.route,null);
});

test('stopping at an unavailable junction does not freeze timeout or following actions',async()=>{
 const vehicle=new Vehicle();const calls=[];
 const queue=new Pipeline(vehicle,async r=>{calls.push(r.stage.action);return {status:'waiting',route:vehicle.pose.xy[0]<1.99?{points:[[vehicle.pose.xy[0],0],[2,0]],segments:[{node_id:'L1',start:0,end:2-vehicle.pose.xy[0]}]}:null,retry_after_m:5,retry_after_s:1,reason:'No straight exit'};});
 queue.add([directStage('go_straight'),directStage('speed_up')],{timeout:5});
 for(let i=0;i<600;i++){vehicle.tick(.01);queue.tick(.01);await Promise.resolve();}
 assert.deepEqual(queue.rows.map(r=>r.status),['timed_out','applied']);
 assert.ok(calls.length>=3);assert.ok(vehicle.pose.xy[0]<=2.01);assert.equal(vehicle.pose.heading,0);
 assert.equal(queue.rows[0].journey.origin.xy[0],0);
});

test('audit retains waiting motion before a route is installed',async()=>{
 const vehicle=new Vehicle();vehicle.install(straight());vehicle.speed=5;let resolve;
 const queue=new Pipeline(vehicle,()=>new Promise(r=>resolve=r));queue.add([directStage('go_straight')]);queue.tick(.01);
 drive(vehicle,queue,2);resolve({status:'ready',route:straight(),maneuver_start_m:12,completion_m:25});await Promise.resolve();
 drive(vehicle,queue,5);const trace=queue.rows[0].journey;
 assert.equal(trace.origin.xy[0],0);assert.ok(trace.samples.some(x=>x.phase==='planning' && x.distance>5));
 assert.ok(trace.samples.some(x=>x.phase==='executing'));assert.equal(queue.rows[0].status,'completed');
});
