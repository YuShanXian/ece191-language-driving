"""Generate optional local replay maps from the current scene loader."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'unit'))
from fixtures import load_scene
out = Path(__file__).resolve().parents[2] / 'review-data-full/maps'
out.mkdir(parents=True, exist_ok=True)
for number in range(1, 8):
    (out / f'{number}.json').write_text(json.dumps({'scene': number, 'roads': load_scene(number).roads}), encoding='utf-8')
