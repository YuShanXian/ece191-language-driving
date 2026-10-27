import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Vehicle} from '../../web/motion.js';
import {motionStatus} from '../../web/motion-status.js';
test('reverse limit is visible and a new forward route releases it', () => {
  const v = new Vehicle();
  assert.ok(v.install({points:[[0,0],[-100,0]],reverse:true,geometry_source:'traveled_path'}, {speedCap:1.5}));
  for(let i=0;i<100;i++)v.tick(.1);
  assert.equal(v.speed,1.5);
  assert.match(motionStatus(v), /Reverse.*5.4 km\/h.*reverse cap 5.4 km\/h/);
  assert.match(motionStatus(v), /Retracing traveled path/);
  v.speed=0;
  const x=v.pose.xy[0];
  assert.ok(v.install({points:[[x,0],[x+100,0]],geometry_source:'mapped_connector'}));
  for(let i=0;i<100;i++)v.tick(.1);
  assert.equal(v.speed,v.target);
  assert.match(motionStatus(v),/Forward.*20.0 km\/h/);
  assert.match(motionStatus(v),/Maneuver uses mapped connection/);
});
