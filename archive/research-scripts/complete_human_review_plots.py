import subprocess,sys
from mtr_project.paths import ROOT
folder=ROOT/'runs/project-v3/language-choice-v1/report-reviewed/human-review'
for scene in range(1,8):
 for command in range(5):
  if (folder/f'scene-{scene:02d}-command-{command}.png').exists():continue
  subprocess.run([sys.executable,str(ROOT/'scripts/render_human_review.py'),'--scene',str(scene),'--command',str(command)],check=True)
print('All 35 neutral review plots ready')
