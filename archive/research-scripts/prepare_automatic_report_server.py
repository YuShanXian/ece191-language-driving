from pathlib import Path
p=Path('historical-project/scripts/serve_human_target_report.py');s=p.read_text().replace('human-target-v8','automatic-road-v9').replace('8772','8773');Path('historical-project/scripts/serve_automatic_road_report.py').write_text(s)
