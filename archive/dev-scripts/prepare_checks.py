from pathlib import Path
root=Path(__file__).parents[1]
for p in (root/'tests').glob('*'):
    if p.suffix not in ('.py','.mjs'):continue
    data=p.read_text(encoding='utf-8')
    p.write_text(data.replace('refactor-v31','refactor-v31'),encoding='utf-8')
