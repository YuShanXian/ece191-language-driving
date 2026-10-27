import json
from pathlib import Path
from parser_backends import ROOT,MODELS
path=ROOT/'runs/project-v3/recording-demo-v1/index.html'
s=path.read_text(encoding='utf-8')
if 'id="modelSelect"' not in s:
 s=s.replace('<span class="badge">Luna 5.6 · Low &nbsp; | &nbsp; Offline demo</span>','<span class="badge" id="modelBadge">Offline demo</span>')
 s=s.replace('</select></div>','</select> <label for="modelSelect" style="margin-left:20px">Language model </label><select id="modelSelect" aria-label="Language model" disabled style="padding:9px;border:1px solid #cad8e4;border-radius:9px;font:inherit"><option>Loading models…</option></select><span id="modelTiming" style="font-size:13px;margin-left:12px;color:#617486"></span></div>',1)
 s=s.replace('test it with Luna 5.6','test it with the selected model')
 s=s.replace("waiting=true;$('#scene').disabled=true;","waiting=true;$('#modelSelect').disabled=true;$('#scene').disabled=true;")
 s=s.replace("'Luna 5.6 parses the steps; the map planner computes their trajectories.'","'The selected model parses the steps; the map planner computes their trajectories.'")
 s=s.replace('JSON.stringify({instruction:text,scene:data.scene,state:liveState})','JSON.stringify({instruction:text,scene:data.scene,state:liveState,model:$(\'#modelSelect\').value})')
 s=s.replace("execution=r.execution;$('#reply')","$('#modelTiming').textContent='Parser: '+r.model_info.parser_seconds.toFixed(1)+' s · With planning: '+r.model_info.total_seconds.toFixed(1)+' s';execution=r.execution;$('#reply')")
 s=s.replace("finally{waiting=false;","finally{waiting=false;$('#modelSelect').disabled=false;")
 s=s.replace("$('#form').onsubmit=submit;","fetch('/models').then(r=>r.json()).then(c=>{const select=$('#modelSelect');select.replaceChildren(...c.models.filter(m=>m.enabled).map(m=>{const o=document.createElement('option');o.value=m.id;o.textContent=m.label;return o}));select.value=c.default;select.disabled=false;const update=()=>{$('#modelBadge').textContent=select.selectedOptions[0].textContent+' | Offline demo';$('#modelTiming').textContent=''};select.onchange=update;update()}).catch(()=>{$('#modelSelect').innerHTML='<option>Models unavailable</option>'});$('#form').onsubmit=submit;")
 path.write_text(s,encoding='utf-8')
catalog={'default':'gpt-5.6-luna','models':[dict(m,enabled=m['id'] in ['gpt-5.6-luna','gpt-6-luna','claude-haiku-5-5']) for m in MODELS]}
(ROOT/'config/language-parser-v4/demo-models.json').write_text(json.dumps(catalog,indent=2),encoding='utf-8')
