import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {Vehicle,Route,angleDiff} from '../../web/motion.js';
import {Pipeline,directStage} from '../../web/pipeline.js';
const fixture=JSON.parse(await readFile(new URL('../fixtures/user-step8-failed.json',import.meta.url)));
const answer=JSON.parse(await readFile(new URL('../fixtures/user-step8-fixed.json',import.meta.url)));
function setup(){const v=new Vehicle();v.reset(fixture.request.state);v.history=fixture.request.state.history;const events=[];const q=new Pipeline(v,async()=>structuredClone(answer),e=>events.push(structuredClone(e)));q.add([directStage('u_turn')]);return {v,q,events};}
async function tick(v,q){q.tick(.05);await Promise.resolve();await Promise.resolve();v.tick(.05);}
test('three-point maneuver completes all four phases with stopped gear changes',async()=>{
 const {v,q,events}=setup();for(let i=0;i<1200&&q.current;i++)await tick(v,q);
 assert.equal(q.rows[0].status,'completed');assert.equal(v.jumps,0);
 const done=events.find(e=>e.type==='completed');assert.equal(done.phases.length,4);
 assert.deepEqual(done.phases.map(p=>p.reverse),[true,false,true,false]);
 for(const p of done.phases.slice(0,-1))assert.equal(p.finish.speed,0);
 assert.equal(v.pose.node_id,'L63380');assert(Math.abs(angleDiff(v.pose.heading,fixture.request.state.heading))>2.9);
});
for(const phase of [0,1,2])test(`cancelling three-point phase ${phase+1} cannot run its remaining phases`,async()=>{
 const {v,q,events}=setup();for(let i=0;i<1200;i++){await tick(v,q);if(q.current?.phaseIndex===phase&&v.distance>1)break;}
 assert.equal(q.current.phaseIndex,phase);q.cancel();const p=[...v.pose.xy];
 q.add([{...directStage('set_speed'),target_speed_mps:5}]);for(let i=0;i<100;i++)await tick(v,q);
 assert.deepEqual(v.pose.xy,p);assert.equal(v.route,null);
 assert(events.filter(e=>e.type==='route_installed').every(e=>e.phase<=phase));
 assert.equal(events.findLast(e=>e.type==='cancelled').action,'u_turn');
});
test('steered reverse does not fabricate a retraceable forward history',()=>{
 const phase=answer.phases[2],route=new Route(phase.route),v=new Vehicle();v.reset(route.at(0));
 v.history=[[1000,1000],[1001,1001]];assert(v.install(phase.route,{speedCap:1.5}));
 for(let i=0;i<30;i++)v.tick(.05);
 assert.deepEqual(v.history,[v.pose.xy]);assert.equal(v.jumps,0);
});
