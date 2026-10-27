import test from 'node:test';
import assert from 'node:assert/strict';
import {Vehicle} from '../../web/motion.js';
import {Pipeline,directStage} from '../../web/pipeline.js';
import {DriveClock} from '../../web/clock.js';
function fixture() {
 const vehicle=new Vehicle(); vehicle.install({points:[[0,0],[1000,0]],segments:[{node_id:'L1',start:0,end:1000}]});
 vehicle.speed=vehicle.target=5;
 const pipeline=new Pipeline(vehicle,()=>new Promise(()=>{}));
 return {vehicle,pipeline,clock:new DriveClock(0)};
}
test('one-second background callbacks preserve real movement and timeout order',()=>{
 const {vehicle,pipeline,clock}=fixture();
 pipeline.add([directStage('turn_left'),directStage('speed_up')],{timeout:5});
 for(let second=1;second<=7;second++)clock.advance(second*1000,vehicle,pipeline,true);
 assert.ok(vehicle.totalDistance>=35);assert.ok(vehicle.movingSeconds>6.99);
 assert.deepEqual(pipeline.rows.map(r=>r.status),['timed_out','applied']);assert.equal(vehicle.jumps,0);
});
test('animation and heartbeat callbacks never count the same elapsed time twice',()=>{
 const {vehicle,pipeline,clock}=fixture();
 for(let i=1;i<=50;i++){clock.advance(i*20,vehicle,pipeline,true);clock.advance(i*20-5,vehicle,pipeline,true);clock.advance(i*20,vehicle,pipeline,true);}
 assert.ok(Math.abs(vehicle.totalDistance-5)<1e-8);assert.ok(Math.abs(vehicle.movingSeconds-1)<1e-8);
});
test('pause still freezes movement and a long computer suspension is bounded',()=>{
 const {vehicle,pipeline,clock}=fixture();vehicle.paused=true;clock.advance(1000,vehicle,pipeline,true);
 assert.equal(vehicle.totalDistance,0);vehicle.paused=false;clock.advance(61000,vehicle,pipeline,true);
 assert.ok(vehicle.totalDistance<=10.01);assert.equal(vehicle.jumps,0);
});
