from mtr_project.paths import ROOT
p=ROOT/'scripts/serve_recording_demo.cjs';s=p.read_text(encoding='utf-8-sig');s=s.replace('parse_navigation_llm.ps1','parse_navigation_llm_v2.ps1').replace("'-Scene',String(scene)]","'-Scene',String(scene),'-Plan']")
s=s.replace('send(r,200,parsed)',"parsed.execution=JSON.parse(fs.readFileSync(path.join(folder,'execution.json'),'utf8').replace(/^\\uFEFF/,''));send(r,200,parsed)")
p.write_text(s)
p=ROOT/'runs/project-v3/recording-demo-v1/index.html';s=p.read_text(encoding='utf-8-sig')
s=s.replace('Local inspection only; labels are not sent to the model.','Copy a label into chat to test it with Astra. Executability is checked separately.')
s=s.replace('<p id="labelmeta" style="font-size:12px"></p>','<p id="labelmeta" style="font-size:12px"></p><button type="button" id="uselabel">Use this instruction</button>')
s=s.replace('<div class="actions" id="actions"></div>','<div class="actions" id="actions"></div><div id="tasks" style="font-size:14px;margin:10px 0;line-height:1.8"></div>')
s=s.replace('let allScenes,data,selected=', 'let execution=null,duration=12,allScenes,data,selected=')
s=s.replace("const tr=data.trajectories[selected];line(data.guides[selected],'#1c9b85',2,[6,5]);", "const tr=execution?execution.points:data.trajectories[selected];if(!execution)line(data.guides[selected],'#1c9b85',2,[6,5]);")
s=s.replace("t.toFixed(1)+' / 12.0 s'","t.toFixed(1)+' / '+duration.toFixed(1)+' s'")
s=s.replace('Math.min(12,t+(now-last)/1000)','Math.min(duration,t+(now-last)/1000)').replace('if(t===12)','if(t===duration)')
s=s.replace("'Playback complete · '+labels[selected]","'Playback complete · '+(execution?execution.status.replaceAll('_',' '):labels[selected])")
s=s.replace("'Playing · '+labels[selected]","'Playing · '+(execution?'multi-step plan':labels[selected])")
a=s.index('async function submit(');b=s.index("$('#form').onsubmit",a)
s=s[:a]+'''async function submit(e){e?.preventDefault();const text=$('#input').value.trim();if(!text||waiting||!data)return;waiting=true;$('#scene').disabled=true;playing=false;selected=-1;execution=null;t=0;duration=12;document.querySelectorAll('.action').forEach(x=>x.classList.remove('active'));$('#send').disabled=true;$('#pause').disabled=true;$('#replay').disabled=true;$('#tasks').replaceChildren();$('#state').textContent='Understanding and planning…';$('#reply').textContent='Astra parses the steps; the map planner computes their trajectories.';
try{const res=await fetch('/parse',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({instruction:text,scene:data.scene})});const r=await res.json();if(!res.ok)throw Error(r.error);execution=r.execution;$('#reply').textContent=r.explanation;
(r.stages||[]).forEach((st,i)=>{const out=execution.stages.find(x=>x.index===i),line=document.createElement('div');line.textContent=(i+1)+'. '+st.source_clause+' — '+(out?out.status.replaceAll('_',' '):'not started')+(out?.reason?' · '+out.reason:'');$('#tasks').append(line)});
$('#detail').textContent='Scene '+String(data.scene).padStart(2,'0')+' · Replanned from each previous endpoint · Geometry-only execution';
if(execution.points.length>1){selected=0;duration=(execution.points.length-1)*execution.dt;const xs=execution.points.map(p=>p[0]),ys=execution.points.map(p=>p[1]);bounds=[Math.min(-15,...xs)-8,Math.max(30,...xs)+8,Math.min(-15,...ys)-8,Math.max(15,...ys)+8];$('#state').textContent='Playing planned motion · '+execution.status.replaceAll('_',' ');playing=true;$('#pause').disabled=false;$('#replay').disabled=false;$('#pause').textContent='Pause'}else{$('#state').textContent=execution.status.replaceAll('_',' ');}
}catch(e){$('#state').textContent='Could not process instruction';$('#reply').textContent=e.message}finally{waiting=false;$('#scene').disabled=false;$('#send').disabled=false}}
''' +s[b:]
s=s.replace('function switchScene(){','function switchScene(){execution=null;duration=12;$(\'#tasks\').replaceChildren();')
s=s.replace("$('#doplan').onchange=showLabel;","$('#doplan').onchange=showLabel;$('#uselabel').onclick=()=>{if(!waiting){const r=data.doplan.labels[Number($('#doplan').value)];if(r)$('#input').value=r.passenger_instruction}};")
s=s.replace("last=now;draw();requestAnimationFrame(tick)","if(execution&&selected>=0){const stage=execution.stages.find(st=>st.end_point>t/.1)||execution.stages[execution.stages.length-1];document.querySelectorAll('.action').forEach((x,i)=>x.classList.toggle('active',codes[i]===stage?.action));}last=now;draw();requestAnimationFrame(tick)")
s=s.replace('Live language parsing → existing map-based plan → trajectory playback.','Live multi-step parsing → sequential map planning → trajectory playback.')
p.write_text(s)
