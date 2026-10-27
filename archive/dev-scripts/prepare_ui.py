from pathlib import Path
import re
root=Path(__file__).parents[1]
for p in [root.parents[1]/'sim/web/view.js',root.parents[1]/'sim/web/motion-status.js']:
    p.write_text(re.sub(r' / [\u4e00-\u9fff][\u4e00-\u9fff，]*','',p.read_text(encoding='utf-8')),encoding='utf-8')
p=root.parents[1]/'sim/web/index.html'
t=p.read_text(encoding='utf-8').replace('Instruction pipeline · \u6307\u4ee4\u961f\u5217','Instruction pipeline')
t=t.replace('<button data-action="u_turn">','<button data-action="leftmost_lane">Leftmost lane</button><button data-action="rightmost_lane">Rightmost lane</button><button data-action="u_turn">')
t=t.replace('<h2>Instruction pipeline</h2>','<h2>Instruction pipeline</h2><label class="queue-follow"><input id="followQueue" type="checkbox" checked>Follow current instruction</label>')
p.write_text(t,encoding='utf-8')
for p in [root/'deploy.py',root.parents[1]/'sim/server.cjs',root.parents[1]/'sim/web/app.js',root.parents[1]/'sim/README.md']:
    p.write_text(p.read_text(encoding='utf-8').replace('refactor-v34','refactor-v35'),encoding='utf-8')
