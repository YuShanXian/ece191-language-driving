from pathlib import Path
import pickle
root = Path('historical-project')
old = '/mnt/c/Users/local-user/.codex/.chatgpt-projects/g-p-6ac6f7a759548191a8d6ba43f82d6865/mtr-prep'
new = str(root)
for path in [root/'docs/READ_FIRST.txt', root/'runs/real-scene-01/RESULT.txt']:
    text = path.read_text(encoding='utf-8')
    path.write_text(text.replace(old,new), encoding='utf-8')
def replace(value):
    if isinstance(value,str): return value.replace(old,new)
    if isinstance(value,dict): return {replace(k):replace(v) for k,v in value.items()}
    if isinstance(value,list): return [replace(x) for x in value]
    if isinstance(value,tuple): return tuple(replace(x) for x in value)
    return value
cache = root/'samples/val/cache_test_MTR'
paths = [cache/'file_list.pkl', *cache.glob('*___scenario_summary.pkl'), * (cache/'tmp').glob('*.pkl')]
for path in paths:
    with path.open('rb') as f: value=pickle.load(f)
    with path.open('wb') as f: pickle.dump(replace(value),f)
print(f'Updated {len(paths)} cache index files. Historical run JSON/logs retained unchanged.')
