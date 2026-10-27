import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {Vehicle} from '../../web/motion.js';
import {Pipeline,directStage} from '../../web/pipeline.js';
const fixture=JSON.parse(await readFile(new URL('../fixtures/u_turn-failed.json',import.meta.url)));
const fixed=JSON.parse(await readFile(new URL('../fixtures/u_turn-fixed.json',import.meta.url)));
function setup(){
 const v=new Vehicle();v.reset({...fixture.request.state,speed:0});
 v.history=fixture.request.state.history.map(p=>[...p]);
 const events=[];
 const q=new Pipeline(v,async()=>fixed,e=>events.push(structuredClone(e)));
 q.add([directStage('u_turn'),directStage('stop')]);
 return {v,q,events};
}
test('reverse-assisted turnaround stays one instruction and stops between gears',async()=>{
 const {v,q,events}=setup();
 q.tick(.05);await new Promise(r=>setImmediate(r));
 for(let i=0;i<3000&&q.current;i++){v.tick(.05);q.tick(.05);}
 assert.equal(q.current,undefined);
 assert.deepEqual(events.filter(e=>e.type==='completed').map(e=>e.action),['u_turn','stop']);
 const phases=events.filter(e=>e.type==='phase_completed');
 assert.equal(phases.length,2);assert.equal(phases[0].state.speed,0);
 const u=events.find(e=>e.type==='completed');
 assert.equal(u.phases[0].reverse,true);assert.equal(u.phases[1].reverse,false);
 assert.ok(Math.abs(Math.atan2(Math.sin(v.pose.heading-fixture.request.state.heading),Math.cos(v.pose.heading-fixture.request.state.heading)))>2.9);
 assert.equal(v.jumps,0);assert.equal(v.speedCap,15);
});
test('cancelling during the reverse phase cannot start the forward turn',async()=>{
 const {v,q,events}=setup();q.tick(.05);await new Promise(r=>setImmediate(r));
 for(let i=0;i<30;i++){v.tick(.05);q.tick(.05);}
 q.cancel();const pose=structuredClone(v.pose);
 for(let i=0;i<1000;i++){v.tick(.05);q.tick(.05);}
 assert.deepEqual(v.pose,pose);assert.equal(events.filter(e=>e.type==='phase_completed').length,0);
});
test('repeated sub-centimeter endpoint routes cannot rotate a stationary vehicle',()=>{
 const v=new Vehicle();v.reset({xy:[203.1284,-13.8798],heading:-.071,speed:0});
 for(let i=0;i<30;i++){
  assert.equal(v.install({points:[[203.1284,-13.8798],[203.1285,-13.8798]],segments:[]}),false);
  v.tick(.1);
 }
 assert.equal(v.pose.heading,-.071);assert.equal(v.movingSeconds,0);
});
test('the next instruction cannot inherit a turn already passed by the vehicle',()=>{
 for(const [distance,expected] of [[19.9,1],[20,0],[20.2,0]]){
  const v=new Vehicle();v.install({points:[[0,0],[30,0]],segments:[],
   movements:[{connector:'C_previous',action:'turn_right',start:10,end:20}]});
  v.distance=distance;v.pose=v.route.at(distance);
  const q=new Pipeline(v,()=>new Promise(()=>{}));q.add([directStage('turn_right')]);q.tick(.01);
  assert.equal(q.current.journey.observed_movements.length,expected);
 }
});
