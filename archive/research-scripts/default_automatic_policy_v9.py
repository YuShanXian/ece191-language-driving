from pathlib import Path
p=Path('historical-project/scripts/select_review_instruction.py');s=p.read_text();s=s.replace("policy='instruction_priority'","policy='automatic_roads'").replace("default='instruction_priority'","default='automatic_roads'");p.write_text(s)
