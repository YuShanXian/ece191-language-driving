from pathlib import Path
p=Path('historical-project/runs/project-v3/recording-demo-v1/index.html')
s=p.read_text(encoding='utf-8-sig')
options=''.join(f'<option value="{i}"'+(' selected' if i==7 else '')+f'>Scene {i:02d}</option>' for i in range(1,8))
s=s.replace('</header>','</header><div style="margin-top:16px"><label for="scene">Driving scene </label><select id="scene" aria-label="Driving scene" disabled style="margin-left:10px;padding:9px 16px;border:1px solid #cad8e4;border-radius:9px;background:white;color:#152d43;font:inherit">'+options+'</select></div>')
s=s.replace('let data,selected=','let allScenes,data,selected=')
s=s.replace('waiting=true;playing=false;',"waiting=true;$('#scene').disabled=true;playing=false;")
s=s.replace('JSON.stringify({instruction:text})','JSON.stringify({instruction:text,scene:data.scene})')
s=s.replace("'Scene 07 · Requested action highlighted above · Existing 12-second plan'","'Scene '+String(data.scene).padStart(2,'0')+' · Requested action highlighted above · Existing 12-second plan'")
s=s.replace("waiting=false;$('#send').disabled=false","waiting=false;$('#scene').disabled=false;$('#send').disabled=false")
start=s.index("fetch('/data.json')")
end=s.index('</script>',start)
s=s[:start]+'''function switchScene(){data=allScenes[$('#scene').value];selected=-1;t=0;playing=false;document.querySelectorAll('.action').forEach(x=>x.classList.remove('active'));$('#pause').disabled=true;$('#replay').disabled=true;$('#pause').textContent='Pause';$('#state').textContent='Ready for your instruction';$('#reply').textContent='Enter an instruction or choose an example to start.';$('#detail').textContent='Scene '+String(data.scene).padStart(2,'0')+' · Same starting position for every command';const pts=data.trajectories.flat(),xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);bounds=[Math.min(-15,...xs)-8,Math.max(30,...xs)+8,Math.min(-15,...ys)-8,Math.max(15,...ys)+8];draw()}
$('#scene').onchange=switchScene;
fetch('/data.json').then(r=>r.json()).then(d=>{allScenes=d.scenes;switchScene();$('#scene').disabled=false;requestAnimationFrame(tick)}).catch(()=>$('#state').textContent='Scene data could not be loaded');
'''+s[end:]
p.write_text(s,encoding='utf-8')
