import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {Vehicle} from '../../web/motion.js';
import {Pipeline,directStage} from '../../web/pipeline.js';
const {PlannerWorker}=createRequire(import.meta.url)('../../worker-client.cjs');
const worker=new PlannerWorker({script:fileURLToPath(new URL('../../worker.py',import.meta.url))});
const results=[];
try {
 for (const mode of ['exact_pose','left_cancel_right','right_cancel_left','left_cancel_straight','later_cancel_right']) {
  const v=new Vehicle(),events=[],q=new Pipeline(v,r=>worker.request(r),e=>events.push(structuredClone(e)));
  async function tick(){q.tick(.05);while(q.pending)await new Promise(r=>setTimeout(r,5));v.tick(.05);}
  if(mode==='exact_pose'){
   const f=JSON.parse(await readFile(new URL('../results/cancel-right-failed.json',import.meta.url)));
   v.reset(f.request.state);v.history=f.request.state.history;
  }else{
   q.add([directStage(mode.startsWith('right')?'turn_right':'turn_left')]);
   // The tight right connector starts rotating earlier than the broad left.
   // Cancel while still uncommitted; late cancellation rejection is tested in Python.
   while(v.totalDistance<(mode.startsWith('right')?4:mode.startsWith('later')?19.2:7))await tick();
   q.cancel();
  }
  const start=structuredClone(v.pose),action=mode.endsWith('left')?'turn_left':mode.endsWith('straight')?'go_straight':'turn_right';
  q.add([directStage(action),directStage('stop')]);
  let elapsed=0;while(q.current&&elapsed<90){await tick();elapsed+=.05;if(q.blocked)break;}
  assert.deepEqual(q.rows.slice(-2).map(r=>r.status),['completed','completed'],mode);
  assert.equal(v.jumps,0);
  const complete=events.findLast(e=>e.type==='completed'&&e.action===action);
  assert(complete.journey.observed_movements.every(m=>m.action===action||m.action==='go_straight'||m.road_bend));
  results.push({mode,start,elapsed,events,rows:q.rows,jumps:v.jumps});
  console.log('PASS',mode,elapsed,v.state().xy);
 }
 await writeFile(new URL('../results/cancel-integration.json',import.meta.url),JSON.stringify(results,null,2));
}finally{worker.close();}
