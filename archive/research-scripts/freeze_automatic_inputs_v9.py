from pathlib import Path
p=Path('historical-project/scripts/run_automatic_roads_v9.py');s=p.read_text(encoding='utf-8-sig');a=s.index('# Strip inherited');b=s.index("commands=",a);s=s[:a]+"# Frozen, minimal scene inventory: only scene number and source file paths.\nmanifest=json.loads((out/'input-manifest.json').read_text())\n"+s[b:];p.write_text(s)
