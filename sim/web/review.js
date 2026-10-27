import {sampleFrame,formatTime,scored} from './review-core.js';
const $=s=>document.querySelector(s),canvas=$('#replayMap'),ctx=canvas.getContext('2d');
const statuses={completed:'Completed',applied:'Applied',timed_out:'Not executed: timeout',cancelled:'Cancelled',queued:'Still queued',approaching:'Approach unfinished',executing:'Execution unfinished',blocked:'Blocked',error:'Error',unsupported:'Unsupported',skipped:'Skipped'};
let catalog=[],data=null,roads=[],maps=new Map(),current=0,playing=false,lastTime=0,active=null,loadEpoch=0;
let revision=0,markers=[],commandRatings={},dirty=0,saved=0,timer,inFlight=null;
function el(tag,text,className){const e=document.createElement(tag);if(text!=null)e.textContent=text;if(className)e.className=className;return e;}
function error(message){$('#error').hidden=!message;$('#error').textContent=message||'';}
async function get(url,options){const r=await fetch(url,options);const body=await r.json();if(!r.ok)throw Error(body.error||`Request failed (${r.status})`);return body;}
function saveStatus(text,failed=false){$('#saveState').textContent=text;$('#saveState').classList.toggle('failed',failed);$('#retrySave').hidden=!failed;}
function rating(){return {score:$('#score').value?Number($('#score').value):null,verdict:$('#verdict').value,notes:$('#notes').value,commands:structuredClone(commandRatings),markers:structuredClone(markers)};}
function draftKey(){return 'driving-review-draft:'+data.id;}
function changed(){if(!data)return;dirty++;saveStatus('Saving…');try{localStorage.setItem(draftKey(),JSON.stringify({hash:data.source.sha256,rating:rating()}));}catch{}clearTimeout(timer);timer=setTimeout(()=>void save().catch(()=>{}),650);}
async function save(){
 clearTimeout(timer);if(inFlight){await inFlight;if(dirty===saved)return;}
 if(!data||dirty===saved)return;
 const id=data.id,n=dirty,payload=rating();saveStatus('Saving…');
 inFlight=get('/api/review/rating?id='+encodeURIComponent(id),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expectedRevision:revision,rating:payload})});
 try{const r=await inFlight;revision=r.revision;saved=n;
  const meta=catalog.find(c=>c.id===id);meta.review={score:r.rating.score,verdict:r.rating.verdict,updatedAt:r.updatedAt};
  if(saved===dirty){saveStatus('Saved locally · '+new Date(r.updatedAt).toLocaleTimeString());try{localStorage.removeItem(draftKey());}catch{}}
  renderLibrary();
 }catch(e){saveStatus('Not saved — '+e.message,true);throw e;}finally{inFlight=null;}
 if(dirty!==saved)return save();
}
function filtered(){const q=$('#search').value.toLowerCase().trim(),v=$('#version').value,s=$('#sceneFilter').value,r=$('#resultFilter').value,h=$('#reviewFilter').value;
 return catalog.filter(c=>(!v||c.version===v)&&(!s||String(c.scene)===s)&&(!q||`${c.title} ${c.id} ${(c.actions||[]).join(' ')}`.toLowerCase().includes(q))&&(!r||(r==='issues'?c.issue:!c.issue))&&(!h||(h==='unreviewed'?!scored(c.review)&&!c.practice:h==='practice'?c.practice:scored(c.review)&&!c.practice)));
}
function renderLibrary(){const cases=filtered(),list=$('#caseList');list.replaceChildren();$('#caseCount').textContent=`(${cases.length})`;
 const real=catalog.filter(c=>!c.practice),done=real.filter(c=>scored(c.review));$('#progress').textContent=`${done.length} / ${real.length} scored · practice excluded`;
 for(const c of cases){const b=el('button',null,'case-item');b.dataset.caseId=c.id;b.setAttribute('aria-current',String(c.id===data?.id));b.append(el('strong',c.title),el('small',`${c.version} · Scene ${c.scene} · ${c.kind} · ${formatTime(c.duration)}`),el('small',`${c.commandCount} instructions · ${Object.entries(c.summary).map(([k,v])=>`${v} ${k.replaceAll('_',' ')}`).join(', ')}`));
  b.append(el('span',c.practice?'Practice':c.review?`${c.review.score??'—'}/5 · ${c.review.verdict?.replaceAll('_',' ')||'No verdict'}`:c.issue?'Unresolved / failed':'Not scored','badge'+(c.issue?' issue':'')));
  b.onclick=()=>void selectCase(c.id).catch(e=>error(e.message));list.append(b);}
 if(!cases.length)list.append(el('p','No tests match these filters.','empty'));
}
async function selectCase(id){
 const epoch=++loadEpoch;await save();if(epoch!==loadEpoch)return;playing=false;error('');$('#caseTitle').textContent='Loading replay…';
 document.querySelectorAll('.scorecard input,.scorecard select,.scorecard textarea,.scorecard button,.transport button').forEach(e=>e.disabled=true);
 const payload=await get('/api/review/case?id='+encodeURIComponent(id));
 if(!maps.has(payload.case.scene)){const map=await get('/api/review/map?scene='+payload.case.scene);maps.set(payload.case.scene,map.roads);}
 if(epoch!==loadEpoch)return;
 data=payload.case;data.commands.forEach((c,i)=>c.ordinal=i+1);roads=maps.get(data.scene);current=0;active=null;revision=payload.review?.revision||0;dirty=saved=0;
 const valid=payload.review?.caseHash===data.source.sha256;let r=valid?payload.review.rating:{score:null,verdict:'',notes:'',commands:{},markers:[]},draft=null;
 try{draft=JSON.parse(localStorage.getItem(draftKey()));}catch{}
 if(draft?.hash===data.source.sha256)r=draft.rating;
 $('#score').value=r.score??'';$('#verdict').value=r.verdict||'';$('#notes').value=r.notes||'';markers=r.markers||[];commandRatings=r.commands||{};
 $('#caseTitle').textContent=data.title;$('#caseMeta').textContent=`${data.version} · Scene ${data.scene} · ${data.kind}${data.practice?' · PRACTICE':''}`;
 $('#fidelity').textContent=data.fidelity;$('#seek').max=data.duration;$('#seek').value=0;
 $('#source').textContent=`Source: ${data.source.path}\nSHA-256: ${data.source.sha256}${data.seed!=null?' · Seed '+data.seed:''}`;
 saveStatus(valid?'Saved locally · '+new Date(payload.review.updatedAt).toLocaleString():'Not scored yet');
 if(payload.review&&!valid)saveStatus('Previous score belongs to different evidence; please reassess.',true);
 renderCommands();renderMarkers();renderEvents();renderLibrary();history.replaceState(null,'','/review?case='+encodeURIComponent(id));
 document.querySelectorAll('.scorecard input,.scorecard select,.scorecard textarea,.scorecard button,.transport button').forEach(e=>e.disabled=false);
 if(draft?.hash===data.source.sha256){dirty++;saveStatus('Recovered unsaved local draft — click Save review');}
 draw();
}
function jump(t){current=Math.max(0,Math.min(data?.duration||0,t));playing=false;draw();}
function renderCommands(){const parent=$('#commands');parent.replaceChildren();
 for(const c of data.commands){const row=el('div',null,'command');row.dataset.commandId=c.id;const info=el('div');info.append(el('strong',`${c.ordinal}. ${c.label||c.action.replaceAll('_',' ')}`),el('span','Recorded: '+(statuses[c.status]||c.status),'record-status'+(!['completed','applied','cancelled','skipped'].includes(c.status)?' issue':'')),el('p',c.reason||''));
  const actions=el('div',null,'actions');const start=el('button','Start '+formatTime(c.started??c.added??0));start.onclick=()=>jump(c.started??c.added??0);actions.append(start);
  if(c.finished!=null){const end=el('button','Finish '+formatTime(c.finished));end.onclick=()=>jump(c.finished);actions.append(end);}
  const select=el('select');select.setAttribute('aria-label',`Rate instruction ${c.ordinal}`);for(const [value,text] of [['','Not assessed'],['pass','Pass'],['needs_work','Needs work'],['fail','Fail'],['uncertain','Uncertain']]){const option=el('option',text);option.value=value;select.append(option);}select.value=commandRatings[c.id]||'';select.onchange=()=>{commandRatings[c.id]=select.value;changed();};actions.append(select);row.append(info,actions);parent.append(row);
 }
}
function renderMarkers(){const parent=$('#markers');parent.replaceChildren();markers.forEach((m,i)=>{const row=el('div',null,'marker'),b=el('button',formatTime(m.time)),remove=el('button','Remove');b.onclick=()=>jump(m.time);remove.setAttribute('aria-label',`Remove marker ${i+1}`);remove.onclick=()=>{markers.splice(i,1);renderMarkers();changed();};row.append(b,el('span',m.note),remove);parent.append(row);});}
function renderEvents(){const parent=$('#events');parent.replaceChildren();for(const e of data.events){if(!['activated','completed','applied','timed_out','cancelled','blocked','error','route_installed'].includes(e.type))continue;const row=el('div',null,'event'),b=el('button',formatTime(e.t));b.onclick=()=>jump(e.t);row.append(b,el('span',`${e.type.replaceAll('_',' ')} · ${e.action||''}${e.reason?' · '+e.reason:''}`));parent.append(row);}}
function draw(){if(!data)return;const f=sampleFrame(data.frames,current);if(!f)return;
 const w=canvas.clientWidth,h=canvas.clientHeight,dpr=devicePixelRatio||1;if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);}ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
 let center=[f[1],f[2]],scale=w/Number($('#zoom').value);
 if(!$('#followCar').checked){const xs=data.frames.map(p=>p[1]),ys=data.frames.map(p=>p[2]),minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);center=[(minX+maxX)/2,(minY+maxY)/2];scale=Math.min(w/(maxX-minX+35),h/(maxY-minY+35));}
 const point=p=>[w/2+(p[0]-center[0])*scale,h/2-(p[1]-center[1])*scale];
 function line(points,color,width){ctx.beginPath();points.forEach((p,i)=>{const [x,y]=point(p);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke();}
 for(const road of roads){if(road.some(p=>Math.abs((p[0]-center[0])*scale)<w/2+20&&Math.abs((p[1]-center[1])*scale)<h/2+20))line(road,'#cbd7df',1);}
 const trail=data.frames.filter((p,i)=>p[0]<=current&&i%2===0).map(p=>[p[1],p[2]]);trail.push([f[1],f[2]]);line(trail,f[7]?'#8855b2':'#0a9099',2.6);
 const pos=point([f[1],f[2]]);ctx.save();ctx.translate(...pos);ctx.rotate(-f[3]);ctx.fillStyle='#123e59';ctx.fillRect(-12,-6,24,12);ctx.fillStyle='#b7e6ec';ctx.fillRect(4,-4,5,8);ctx.restore();
 const c=data.commands.find(c=>String(c.id)===String(f[5]));$('#currentInstruction').textContent=c?`${c.ordinal}. ${c.label||c.action} · ${String(f[6]).replaceAll('_',' ')}`:current>=data.duration?'Replay finished':'Recorded continuation';
 $('#poseStats').textContent=`${Number.isFinite(f[4])?(f[4]*3.6).toFixed(1)+' km/h':'Speed not recorded'} · (${f[1].toFixed(1)}, ${f[2].toFixed(1)})\n${data.kind==='simulation'?'Verified simulation time':'Interpolated record time'}`;
 $('#seek').value=current;$('#time').textContent=`${formatTime(current)} / ${formatTime(data.duration)}`;$('#play').textContent=playing?'Pause':current>=data.duration?'Replay':'Play';
 if(active!==f[5]){active=f[5];document.querySelectorAll('.command').forEach(e=>{const match=String(e.dataset.commandId)===String(active);e.classList.toggle('active',match);if(match)e.setAttribute('aria-current','step');else e.removeAttribute('aria-current');});}
}
$('#play').onclick=()=>{if(!data)return;if(current>=data.duration)current=0;playing=!playing;lastTime=performance.now();draw();};
$('#restart').onclick=()=>jump(0);$('#stepBack').onclick=()=>jump(current-1);$('#stepForward').onclick=()=>jump(current+1);$('#seek').oninput=()=>jump(Number($('#seek').value));
$('#zoom').onchange=$('#followCar').onchange=draw;window.addEventListener('resize',draw);
for(const id of ['search','version','sceneFilter','resultFilter','reviewFilter'])$('#'+id).addEventListener(id==='search'?'input':'change',renderLibrary);
for(const id of ['score','verdict','notes'])$('#'+id).addEventListener(id==='notes'?'input':'change',changed);
$('#saveNow').onclick=$('#retrySave').onclick=()=>void save().catch(e=>error(e.message));
$('#addMarker').onclick=()=>{if(!data)return;const note=$('#markerNote').value.trim();if(!note){$('#markerNote').focus();return;}markers.push({time:+current.toFixed(2),note});$('#markerNote').value='';renderMarkers();changed();};
$('#nextUnreviewed').onclick=()=>{const cases=filtered().filter(c=>!c.practice&&!scored(c.review)),next=cases.find(c=>c.id!==data?.id);if(next)void selectCase(next.id).catch(e=>error(e.message));else error('No other unreviewed tests match the current filters.');};
window.addEventListener('beforeunload',e=>{if(dirty!==saved){e.preventDefault();e.returnValue='';}});
function frame(now){const dt=Math.min(.2,(now-lastTime)/1000||0);lastTime=now;if(playing&&data){current=Math.min(data.duration,current+dt*Number($('#rate').value));if(current>=data.duration)playing=false;draw();}requestAnimationFrame(frame);}requestAnimationFrame(frame);
try{const index=await get('/api/review/catalog');catalog=index.cases;for(const version of [...new Set(catalog.map(c=>c.version))].sort().reverse()){if(![...$('#version').options].some(o=>o.value===version)){const option=el('option',version);option.value=version;$('#version').append(option);}}renderLibrary();const requested=new URLSearchParams(location.search).get('case'),first=catalog.find(c=>c.id===requested)||catalog.find(c=>c.id==='v40-browser-example-01')||catalog.find(c=>c.id==='v39-browser-main')||catalog.find(c=>c.id==='v38-browser-main')||catalog.find(c=>c.id==='v37-browser-main')||catalog.find(c=>c.id==='v36-browser-main')||catalog[0];if(first){$('#version').value=first.version;await selectCase(first.id);}}catch(e){error('Unable to load review evidence: '+e.message);}
