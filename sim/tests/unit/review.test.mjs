import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdir,readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {sampleFrame,scored,formatTime} from '../../web/review-core.js';
const {ReviewStore}=createRequire(import.meta.url)('../../review-store.cjs');
const dir=fileURLToPath(new URL('../results/review-store-test-'+Date.now()+'/',import.meta.url));
const meta={id:'practice-test',duration:20,source:{sha256:'fixture-hash'}};
const rating={score:4,verdict:'needs_work',notes:'A turn needs review.',commands:{1:'fail'},markers:[{time:4.2,note:'Check exit'}]};
test('review survives a new store instance, with append-only history',async()=>{
 const store=new ReviewStore(dir);await store.save(meta,{expectedRevision:0,rating});
 const restored=await new ReviewStore(dir).read(meta.id);assert.deepEqual(restored.rating,rating);assert.equal(restored.revision,1);
 assert.equal(JSON.parse((await readFile(dir+'history.jsonl','utf8')).trim()).caseHash,'fixture-hash');
});
test('stale concurrent rating cannot silently overwrite another review',async()=>{
 const store=new ReviewStore(dir+'conflict/');await store.save(meta,{expectedRevision:0,rating});
 const both=await Promise.allSettled([store.save(meta,{expectedRevision:1,rating:{...rating,score:5}}),store.save(meta,{expectedRevision:1,rating:{...rating,score:1}})]);
 assert.equal(both.filter(x=>x.status==='fulfilled').length,1);assert.equal(both.find(x=>x.status==='rejected').reason.status,409);
 assert.equal((await store.read(meta.id)).rating.score,5);
});
test('bad scores and out-of-record markers are rejected without writing',async()=>{
 const store=new ReviewStore(dir+'invalid/');
 for(const bad of [{...rating,score:6},{...rating,score:0},{...rating,verdict:'auto_pass'},{...rating,markers:[{time:30,note:'out of bounds'}]}])await assert.rejects(store.save(meta,{expectedRevision:0,rating:bad}),e=>e.status===400);
 assert.equal(await store.read(meta.id),null);
});
test('seeking preserves orientation through the pi boundary and exposes missing speed',()=>{
 const frames=[[0,0,0,Math.PI-.1,2,1,'executing',false],[10,10,0,-Math.PI+.1,4,2,'waiting',false]];
 const f=sampleFrame(frames,5);assert(Math.abs(f[3]-Math.PI)<1e-9);assert.equal(f[1],5);assert.equal(f[5],1);
 assert.equal(sampleFrame(frames,10)[5],2);assert.equal(sampleFrame(frames,-4)[1],0);assert.equal(sampleFrame(frames,30)[1],10);
 frames[0][4]=null;assert.equal(sampleFrame(frames,5)[4],null);
});
test('notes alone are not counted as a completed human score',()=>{
 assert.equal(scored({score:null,verdict:''}),false);assert.equal(scored({score:1,verdict:''}),true);assert.equal(scored({score:null,verdict:'uncertain'}),true);
});
test('rounded timestamps carry into the next minute',()=>{
 assert.equal(formatTime(59.96),'1:00.0');assert.equal(formatTime(119.99),'2:00.0');
});
test('all imported cases have finite, ordered frames and retain unresolved outcomes',async()=>{
 const root=new URL('../../review-data/',import.meta.url),index=JSON.parse(await readFile(new URL('catalog.json',root)));
 let unresolved=0;
 for(const meta of index.cases){const c=JSON.parse(await readFile(new URL('cases/'+meta.id+'.json',root)));
  assert(c.frames.length>0,c.id);assert.equal(c.duration,c.frames.at(-1)[0]);
  assert(c.frames.every((f,i)=>f.slice(0,4).every(Number.isFinite)&&(!i||f[0]>=c.frames[i-1][0])),c.id);
  assert.equal(new Set(c.commands.map(x=>x.id)).size,c.commands.length,c.id);
  if(c.kind==='browser')assert(c.frames.every(f=>!['telemetry','plan','queued'].includes(f[6])),c.id+': sampling events must not replace execution state');
  unresolved+=c.commands.filter(x=>['timed_out','blocked','error','approaching','queued','executing'].includes(x.status)).length;
 }
 assert.equal(index.cases.length,6);
 assert.deepEqual(index.cases.map(c=>c.id).sort(),Array.from({length:6},(_,i)=>`v40-browser-example-0${i+1}`));
 assert.equal(index.cases.filter(c=>c.kind==='browser').length,6);
});

test('curated replays retain actual ordered maneuvers and a final stop',async()=>{
 const expected=[['go_straight'],['go_straight','stop'],['turn_left','stop'],['turn_right','stop'],
 ['go_straight','lane_change_right','stop'],['go_straight','lane_change_right','lane_change_left','stop']];
 for(let i=0;i<6;i++){
  const c=JSON.parse(await readFile(new URL(`../../review-data/cases/v40-browser-example-0${i+1}.json`,import.meta.url)));
  assert.deepEqual(c.commands.map(x=>x.action),expected[i]);
  assert(c.commands.every(x=>['completed','applied'].includes(x.status)));
  assert(c.frames.at(-1)[4]<.02);
 }
});
